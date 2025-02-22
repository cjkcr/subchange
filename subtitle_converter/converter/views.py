from django.shortcuts import render
from django.http import HttpResponse
import pysubs2
import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from googletrans import Translator
import asyncio
import re
import logging
from urllib.parse import quote

logger = logging.getLogger("converter")

async def translate_text_bulk(texts, target_language):
    """
    使用 googletrans 批量翻译文本列表到目标语言.
    在翻译前后都进行文本清洗，彻底移除多余的回车、转义字符和孤立的 'n'、'\\N'。

    """
    translator = Translator()
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

        # 批量翻译清洗后的文本列表
        translated_results = await translator.translate(cleaned_texts, dest=target_language)
        # 提取翻译后的文本
        translated_texts_pre_clean = [result.text for result in translated_results] # 翻译后的文本，先保存到临时列表

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

    except Exception as e:
        print(f"批量翻译错误: {e}")
        # 如果翻译失败，返回原始文本列表，保证后续处理不中断
        return texts

async def subtitle_convert_and_download(subs, subtitle_format, response_filename, target_language):

    
    """
    将字幕转换为指定格式并提供下载，实现批量翻译和双语字幕。
    :param subs: pysubs2 字幕对象
    :param subtitle_format: 用户选择的输出格式 (srt, ass, ssa, vtt, sub)
    :param response_filename: 转换后的字幕文件名
    :param target_language: 用户选择的目标语言（如 'en'，'zh' 等）
    :return: HttpResponse 对象，包含转换后的文件内容
    """
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
        translated_segments = await translate_text_bulk(text_segments_to_translate, target_language)
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
            
            # 构建双语字幕行：原始文本 + 换行符 + 翻译文本
            line.text = translated_text_line + "\n" + cleaned_text_line
            # print(f"双语字幕行: {line.text}") # 打印双语字幕行

    # 后续处理 (保存文件和返回 response) 与之前代码相同
    converted_file_path = f"/tmp/{response_filename}"

    if subtitle_format == 'srt':
        subs.save(converted_file_path, format='srt')
    elif subtitle_format == 'ass':
        subs.save(converted_file_path, format='ass')
    elif subtitle_format == 'ssa':
        subs.save(converted_file_path, format='ssa')
    elif subtitle_format == 'vtt':
        subs.save(converted_file_path, format='vtt')
    elif subtitle_format == 'sub':
        subs.save(converted_file_path, format='sub')

    with open(converted_file_path, 'rb') as f:
        converted_subtitle = f.read()
    # 准备下载文件
    response = HttpResponse(converted_subtitle, content_type='text/plain') 

    # 对文件名进行 URL 编码
    encoded_filename = quote(response_filename.encode('utf-8'))

    # 设置 Content-Disposition 头
    response['Content-Disposition'] = (f'attachment; filename="{encoded_filename}";'f'filename*=UTF-8\'\'{encoded_filename}')   
   


    # 使用 quote() 对文件名进行 URL 编码
    # response['Content-Disposition'] = f'attachment; filename="{quote(response_filename)}"'
    # 下载准备日志记录 
    logger.info(f"字幕文件 '{response_filename}' 译成 '{target_language}' 以 '{subtitle_format}' 格式转换成功，准备提供下载。")
    os.remove(converted_file_path)
    return response


async def subtitle_convert(request):
    if request.method == 'POST' and request.FILES['subtitle']:
        subtitle_file = request.FILES['subtitle']
        subtitle_format = request.POST['format']
        target_language = request.POST['target_language']
        custom_filename = request.POST.get('custom_filename', 'converted')
        if not custom_filename:
            custom_filename = os.path.splitext(subtitle_file.name)[0]

        temp_path = default_storage.save(subtitle_file.name, ContentFile(subtitle_file.read()))
        subs = pysubs2.load(temp_path)

        response = await subtitle_convert_and_download(subs, subtitle_format, f"{custom_filename}.{subtitle_format}", target_language)

        default_storage.delete(temp_path)
        return response

    return render(request, 'converter/upload.html')