from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import pysubs2
import os
import asyncio
import re
import logging
import codecs
import requests
import tempfile
import time
from urllib.parse import quote
import uuid

logger = logging.getLogger("converter")

GOOGLE_TRANSLATE_URL = "https://clients5.google.com/translate_a/t"
TRANSLATION_BATCH_ITEMS = 20
TRANSLATION_BATCH_CHARS = 1800
TRANSLATION_TOTAL_TIMEOUT = 240
MAX_UPLOAD_SIZE = 5 * 1024 * 1024
SUPPORTED_EXTENSIONS = {'.srt', '.ass', '.ssa', '.vtt'}
SUPPORTED_TARGET_LANGUAGES = {'none', 'en', 'zh-cn', 'es', 'fr'}
SUPPORTED_TRANSLATION_MODES = {'bilingual', 'translated'}
JOB_TTL_SECONDS = 15 * 60
MAX_ACTIVE_JOBS = 8

job_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='subchange-job')
job_lock = Lock()
conversion_jobs = {}


class TranslationError(Exception):
    """Raised when the upstream translation service cannot return valid data."""


def _load_subtitles(path):
    """Read common subtitle encodings without assuming every upload is UTF-8."""
    with open(path, 'rb') as subtitle_file:
        content = subtitle_file.read()
    sample = content[:4096]

    if content.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        encoding = 'utf-32'
    elif content.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        encoding = 'utf-16'
    elif content.startswith(codecs.BOM_UTF8):
        encoding = 'utf-8-sig'
    elif sample.count(b'\x00') > len(sample) // 4:
        encoding = 'utf-16-le' if sample[1::2].count(0) > sample[::2].count(0) else 'utf-16-be'
    else:
        try:
            content.decode('utf-8')
            encoding = 'utf-8'
        except UnicodeDecodeError:
            content.decode('gb18030')
            encoding = 'gb18030'

    return pysubs2.load(path, encoding=encoding)


def _remove_file(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            logger.exception("临时文件删除失败: %s", path)


def _cleanup_expired_jobs():
    cutoff = time.time() - JOB_TTL_SECONDS
    expired = []
    with job_lock:
        for job_id, job in conversion_jobs.items():
            if job['status'] in {'done', 'error'} and job['updated_at'] < cutoff:
                expired.append((job_id, job.get('output_path')))
        for job_id, _ in expired:
            conversion_jobs.pop(job_id, None)
    for _, output_path in expired:
        _remove_file(output_path)


def _update_job(job_id, **changes):
    with job_lock:
        job = conversion_jobs.get(job_id)
        if not job:
            return
        job.update(changes)
        job['updated_at'] = time.time()


def _content_disposition(filename):
    encoded_filename = quote(filename.encode('utf-8'))
    return (
        f'attachment; filename="{encoded_filename}";'
        f"filename*=UTF-8''{encoded_filename}"
    )


def _translation_batches(texts):
    batch = []
    char_count = 0

    for text in texts:
        if batch and (
            len(batch) >= TRANSLATION_BATCH_ITEMS
            or char_count + len(text) > TRANSLATION_BATCH_CHARS
        ):
            yield batch
            batch = []
            char_count = 0

        batch.append(text)
        char_count += len(text)

    if batch:
        yield batch


def _request_translation_batch(texts, target_language):
    params = [
        ("client", "dict-chrome-ex"),
        ("sl", "auto"),
        ("tl", target_language),
    ]
    params.extend(("q", text) for text in texts)

    response = requests.get(
        GOOGLE_TRANSLATE_URL,
        params=params,
        timeout=(5, 30),
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    payload = response.json()

    if not isinstance(payload, list) or len(payload) != len(texts):
        raise TranslationError("翻译服务返回了不完整的数据")

    translated = []
    for item in payload:
        if not isinstance(item, list) or not item or not isinstance(item[0], str):
            raise TranslationError("翻译服务返回了无法识别的数据")
        translated.append(item[0])

    return translated

async def translate_text_bulk(texts, target_language, progress_callback=None):
    """
    分批调用 Google Chrome 翻译端点，避免 googletrans 在被限流时无限等待。
    在翻译前后都进行文本清洗，彻底移除多余的回车、转义字符和孤立的 'n'、'\\N'。
    """
    try:
        cleaned_texts = []
        for text in texts:
            # print(f"原文片段 (清洗前): {text}") # 打印清洗前的原文片段
            # 1. 翻译前清洗：移除多余的反斜杠转义字符和回车符
            cleaned_text = text.replace('\\\\', '')
            cleaned_text = cleaned_text.replace('\\N', ' ')
            # cleaned_text = cleaned_text.replace('\\', '')
            cleaned_text = cleaned_text.replace('\n', ' ')            
            cleaned_text = cleaned_text.replace('\r\n', ' ')
            cleaned_text = cleaned_text.replace('\\n', ' ')
            
            # print(f"原文片段 (清洗后): {cleaned_text}") # 打印清洗后的原文片段
            cleaned_texts.append(cleaned_text)

        if not cleaned_texts:
            return [], []

        async def translate_all_batches():
            results = []
            batches = list(_translation_batches(cleaned_texts))
            for index, batch in enumerate(batches, start=1):
                translated_batch = await asyncio.to_thread(
                    _request_translation_batch,
                    batch,
                    target_language,
                )
                results.extend(translated_batch)
                if progress_callback:
                    progress_callback(index, len(batches))
            return results

        translated_texts_pre_clean = await asyncio.wait_for(
            translate_all_batches(),
            timeout=TRANSLATION_TOTAL_TIMEOUT,
        )

        translated_texts_post_clean = [] # 存储最终清洗后的翻译文本
        for text in translated_texts_pre_clean:
            # print(f"翻译结果 (清洗前): {text}") # 打印翻译结果清洗前的文本
            # 2. 翻译后清洗：移除孤立的 'n' 字符
            cleaned_text = re.sub(r'\bn\b', '', text, flags=re.IGNORECASE) # 使用正则移除单词边界的 'n' (忽略大小写)
            cleaned_text = cleaned_text.replace('  ', ' ') #  移除多余的空格，避免因移除 'n' 产生双空格
            cleaned_text = cleaned_text.replace('{\ i1}', '{\i1}')
            cleaned_text = cleaned_text.replace('{\i1}，', '{\i1}')
            cleaned_text = cleaned_text.replace('{\ i0}', '{\i0}')
            cleaned_text = cleaned_text.strip() # 移除首尾空格
            # print(f"翻译结果 (清洗后): {cleaned_text}") # 打印翻译结果清洗后的文本
            translated_texts_post_clean.append(cleaned_text)

        return translated_texts_post_clean, cleaned_texts # 返回最终清洗后的翻译文本

    except asyncio.TimeoutError as exc:
        logger.exception("翻译请求超过总时限")
        raise TranslationError("翻译服务响应超时，请缩短字幕后重试") from exc
    except TranslationError:
        logger.exception("翻译服务返回异常")
        raise
    except (requests.RequestException, ValueError) as exc:
        logger.exception("翻译接口请求失败")
        raise TranslationError("翻译服务暂时不可用，请稍后重试") from exc

async def subtitle_convert_and_download(
    subs,
    subtitle_format,
    custom_filename,
    target_language,
    translation_mode='bilingual',
    append_unique_suffix=True,
    progress_callback=None,
):

    
    """
    将字幕转换为指定格式并提供下载，实现批量翻译和双语字幕。
    :param subs: pysubs2 字幕对象
    :param subtitle_format: 用户选择的输出格式 (srt, ass, ssa, vtt)
    :param response_filename: 转换后的字幕文件名
    :param target_language: 用户选择的目标语言（如 'en'，'zh' 等）
    :param translation_mode: bilingual 为译文加原文，translated 为仅保留译文
    :return: HttpResponse 对象，包含转换后的文件内容
    """
    if progress_callback:
        progress_callback(12, 'Reading subtitle structure')

    if target_language != 'none':
        text_segments_to_translate = []
        original_segments_structure = []

        # 1. 提取所有需要翻译的文本段和原始分段结构
        for line in subs:
            line_segments = []
            parts = re.findall(r'(\[.*?\])|(<i>.*?</i>)|([^\[\<]+)', line.text)
            original_line_parts = []

            for part in parts:
                tag_content_square_bracket = part[0]
                tag_content_italic = part[1]
                plain_text = part[2]

                if tag_content_square_bracket:
                    text_segments_to_translate.append(tag_content_square_bracket[1:-1])
                    line_segments.append({'type': 'square_bracket', 'original_tag': tag_content_square_bracket})
                    original_line_parts.append(tag_content_square_bracket)
                elif tag_content_italic:
                    # 修改：将 <i> 标签内的多行文本合成为单行，用空格连接
                    italic_text_content = tag_content_italic[3:-4]
                    cleaned_italic_text = ' '.join(italic_text_content.splitlines()) # 合成单行
                    text_segments_to_translate.append(cleaned_italic_text)
                    line_segments.append({'type': 'italic', 'original_tag': tag_content_italic})
                    # original_line_parts.append("<i>" + tag_content_italic + "</i>")
                    original_line_parts.append(tag_content_italic)
                elif plain_text:
                    text_segments_to_translate.append(plain_text)
                    line_segments.append({'type': 'plain'})
                    original_line_parts.append(plain_text)
            original_segments_structure.append(line_segments)
            line.original_text = "".join(original_line_parts)

        # 2. 批量翻译清洗后的文本
        def report_translation(completed, total):
            if progress_callback:
                percent = 18 + round(67 * completed / max(total, 1))
                progress_callback(percent, f'Translating batch {completed} of {total}')

        translated_segments = await translate_text_bulk(
            text_segments_to_translate,
            target_language,
            report_translation,
        )
        translated_segments_list, cleaned_texts_list = translated_segments # 解包返回的元组
        # 分别为这两个列表创建迭代器
        translated_segments_iterator = iter(translated_segments_list)
        cleaned_texts_iterator = iter(cleaned_texts_list)


        
        # 3. 将翻译后的文本放回字幕行，并构建双语字幕
        for i, line in enumerate(subs):
            translated_line_parts = []
            cleaned_text_part = []
            for segment_info in original_segments_structure[i]:
                segment_type = segment_info['type']
                if segment_type == 'square_bracket':
                    translated_text = next(translated_segments_iterator)                    
                    translated_line_parts.append(f"[{translated_text}]")
                    cleaned_text = next(cleaned_texts_iterator)
                    cleaned_text_part.append(f"[{cleaned_text}]")
                elif segment_type == 'italic':
                    translated_text = next(translated_segments_iterator)
                    translated_line_parts.append(translated_text)
                    # translated_line_parts.append("<i>"+f"{translated_text}"+"</i>")
                    cleaned_text = next(cleaned_texts_iterator)
                    cleaned_text_part.append(cleaned_text)

                elif segment_type == 'plain':
                    translated_text = next(translated_segments_iterator)
                    translated_line_parts.append(translated_text)
                    cleaned_text = next(cleaned_texts_iterator)
                    cleaned_text_part.append(cleaned_text)
            translated_text_line = "".join(translated_line_parts)
            cleaned_text_line = "".join(cleaned_text_part)
            
            if translation_mode == 'translated':
                line.text = translated_text_line
            else:
                # 构建双语字幕行：译文 + 换行符 + 原文
                line.text = translated_text_line + "\n" + cleaned_text_line
            # print(f"双语字幕行: {line.text}") # 打印双语字幕行

        if progress_callback:
            progress_callback(90, 'Assembling translated subtitles')
    elif progress_callback:
        progress_callback(85, 'Preparing converted subtitles')

    # 后续处理 (保存文件和返回 response) 与之前代码相同
    # 生成唯一的文件名
    unique_id = uuid.uuid4().hex[:8]  # 自动命名时避免浏览器下载重名
    if custom_filename:
        suffix = f"_{unique_id}" if append_unique_suffix else ""
        response_filename = f"{custom_filename}{suffix}.{subtitle_format}"
    else:
        # 如果没有自定义文件名，使用默认前缀加上 UUID
        response_filename = f"converted_{unique_id}.{subtitle_format}"

    with tempfile.NamedTemporaryFile(
        prefix='subchange-output-',
        suffix=f'.{subtitle_format}',
        delete=False,
    ) as converted_file:
        converted_file_path = converted_file.name

    try:
        if progress_callback:
            progress_callback(94, 'Writing output file')
        subs.save(converted_file_path, format=subtitle_format)
        with open(converted_file_path, 'rb') as f:
            converted_subtitle = f.read()

        response = HttpResponse(converted_subtitle, content_type='text/plain')
        response['Content-Disposition'] = _content_disposition(response_filename)
        response.subchange_filename = response_filename
        if progress_callback:
            progress_callback(97, 'Finalizing download')
        logger.info(
            "字幕文件 '%s' 译成 '%s' 以 '%s' 格式转换成功，准备提供下载。",
            response_filename,
            target_language,
            subtitle_format,
        )
        return response
    finally:
        if os.path.exists(converted_file_path):
            os.remove(converted_file_path)


def _run_conversion_job(
    job_id,
    temp_path,
    subtitle_format,
    custom_filename,
    target_language,
    translation_mode,
    append_unique_suffix,
):
    output_path = None
    try:
        _update_job(job_id, status='processing', progress=8, message='Loading subtitle file')
        subs = _load_subtitles(temp_path)

        def report_progress(percent, message):
            _update_job(
                job_id,
                progress=max(8, min(int(percent), 99)),
                message=message,
            )

        response = asyncio.run(
            subtitle_convert_and_download(
                subs,
                subtitle_format,
                custom_filename,
                target_language,
                translation_mode,
                append_unique_suffix,
                report_progress,
            )
        )

        with tempfile.NamedTemporaryFile(
            prefix='subchange-job-output-',
            suffix=f'.{subtitle_format}',
            delete=False,
        ) as output_file:
            output_file.write(response.content)
            output_path = output_file.name

        _update_job(
            job_id,
            status='done',
            progress=100,
            message='Download ready',
            output_path=output_path,
            filename=response.subchange_filename,
        )
    except TranslationError as exc:
        _remove_file(output_path)
        _update_job(
            job_id,
            status='error',
            progress=100,
            message=f'翻译失败：{exc}',
        )
    except Exception:
        _remove_file(output_path)
        logger.exception("后台字幕转换失败")
        _update_job(
            job_id,
            status='error',
            progress=100,
            message='字幕文件无法处理，请检查文件格式后重试',
        )
    finally:
        _remove_file(temp_path)


def conversion_progress(request, job_id):
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    _cleanup_expired_jobs()
    job_key = str(job_id)
    with job_lock:
        job = conversion_jobs.get(job_key)
        if not job:
            return JsonResponse({'error': '转换任务不存在或已过期'}, status=404)
        payload = {
            'status': job['status'],
            'progress': job['progress'],
            'message': job['message'],
        }
        if job['status'] == 'done':
            payload['filename'] = job['filename']
            payload['download_url'] = reverse(
                'conversion_download',
                kwargs={'job_id': job_id},
            )

    response = JsonResponse(payload)
    response['Cache-Control'] = 'no-store'
    return response


def conversion_download(request, job_id):
    if request.method != 'GET':
        return HttpResponse("Method not allowed", status=405)

    job_key = str(job_id)
    with job_lock:
        job = conversion_jobs.get(job_key)
        if not job:
            return HttpResponse("转换任务不存在或已过期", status=404)
        if job['status'] != 'done':
            return HttpResponse("转换任务尚未完成", status=409)
        output_path = job.get('output_path')
        filename = job.get('filename', 'converted.srt')

    try:
        with open(output_path, 'rb') as output_file:
            content = output_file.read()
    except OSError:
        logger.exception("转换结果读取失败: %s", output_path)
        return HttpResponse("转换结果已失效，请重新转换", status=410)

    with job_lock:
        conversion_jobs.pop(job_key, None)
    _remove_file(output_path)

    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = _content_disposition(filename)
    response['Cache-Control'] = 'no-store'
    return response


async def subtitle_convert(request):
    if request.method == 'POST':
        subtitle_file = request.FILES.get('subtitle')
        if not subtitle_file:
            return HttpResponse("请选择字幕文件", status=400)
        if subtitle_file.size > MAX_UPLOAD_SIZE:
            return HttpResponse("字幕文件不能超过 5 MB", status=413)

        source_extension = os.path.splitext(subtitle_file.name)[1].lower()
        if source_extension not in SUPPORTED_EXTENSIONS:
            return HttpResponse("不支持的字幕文件类型", status=400)

        subtitle_format = request.POST.get('format', 'srt')
        target_language = request.POST.get('target_language', 'none')
        translation_mode = request.POST.get('translation_mode', 'bilingual')
        if subtitle_format not in {'srt', 'ass', 'ssa', 'vtt'}:
            return HttpResponse("不支持的输出格式", status=400)
        if target_language not in SUPPORTED_TARGET_LANGUAGES:
            return HttpResponse("不支持的目标语言", status=400)
        if translation_mode not in SUPPORTED_TRANSLATION_MODES:
            return HttpResponse("不支持的翻译输出模式", status=400)

        requested_filename = request.POST.get('custom_filename', '').strip()
        append_unique_suffix = not bool(requested_filename)
        custom_filename = requested_filename or os.path.splitext(subtitle_file.name)[0]
        custom_filename = os.path.basename(custom_filename)
        custom_filename = re.sub(r'[^\w.-]+', '_', custom_filename)[:100] or 'converted'

        use_background_job = request.POST.get('async_job') == '1'
        if use_background_job:
            _cleanup_expired_jobs()
            with job_lock:
                active_jobs = sum(
                    job['status'] in {'queued', 'processing'}
                    for job in conversion_jobs.values()
                )
            if active_jobs >= MAX_ACTIVE_JOBS:
                return JsonResponse(
                    {'error': '服务器正在处理较多任务，请稍后重试'},
                    status=429,
                )

        with tempfile.NamedTemporaryFile(
            prefix='subchange-upload-',
            suffix=source_extension,
            delete=False,
        ) as uploaded_file:
            for chunk in subtitle_file.chunks():
                uploaded_file.write(chunk)
            temp_path = uploaded_file.name

        if use_background_job:
            job_id = str(uuid.uuid4())
            now = time.time()
            with job_lock:
                conversion_jobs[job_id] = {
                    'status': 'queued',
                    'progress': 5,
                    'message': 'Upload complete; waiting to process',
                    'created_at': now,
                    'updated_at': now,
                    'output_path': None,
                    'filename': None,
                }
            try:
                job_executor.submit(
                    _run_conversion_job,
                    job_id,
                    temp_path,
                    subtitle_format,
                    custom_filename,
                    target_language,
                    translation_mode,
                    append_unique_suffix,
                )
            except Exception:
                with job_lock:
                    conversion_jobs.pop(job_id, None)
                _remove_file(temp_path)
                logger.exception("字幕转换任务提交失败")
                return JsonResponse({'error': '转换任务无法启动，请稍后重试'}, status=503)

            response = JsonResponse(
                {
                    'job_id': job_id,
                    'progress_url': reverse(
                        'conversion_progress',
                        kwargs={'job_id': job_id},
                    ),
                },
                status=202,
            )
            response['Cache-Control'] = 'no-store'
            return response

        try:
            subs = _load_subtitles(temp_path)
            return await subtitle_convert_and_download(
                subs,
                subtitle_format,
                custom_filename,
                target_language,
                translation_mode,
                append_unique_suffix,
            )
        except TranslationError as exc:
            return HttpResponse(f"翻译失败：{exc}", status=502)
        except Exception:
            logger.exception("字幕转换失败")
            return HttpResponse("字幕文件无法处理，请检查文件格式后重试", status=400)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    return render(request, 'converter/upload.html')
