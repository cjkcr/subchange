from django.shortcuts import render
from django.http import HttpResponse
import pysubs2
import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from googletrans import Translator
import asyncio
from langdetect import detect
import re

async def translate_text_bulk(texts, target_language):
    """
    使用 googletrans 批量翻译文本列表到目标语言.
    """
    translator = Translator()
    try:
        # 批量翻译文本列表
        translated_results = await translator.translate(texts, dest=target_language)
        # 提取翻译后的文本
        translated_texts = [result.text for result in translated_results]
        return translated_texts
    except Exception as e:
        print(f"批量翻译错误: {e}")
        # 发生错误时返回原始文本列表，保证后续处理不中断
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
        text_segments_to_translate = [] # 存储所有待翻译的文本段
        original_segments_structure = [] # 存储原始字幕行的分段结构，用于重建原始行和翻译行

        # 1. 提取所有需要翻译的文本段和原始分段结构
        for line in subs:
            line_segments = [] # 存储当前行的分段信息
            parts = re.findall(r'(\[.*?\])|(<i>.*?</i>)|([^\[\<]+)', line.text)
            original_line_parts = [] # 用于构建原始字幕行文本

            for part in parts:
                tag_content_square_bracket = part[0]
                tag_content_italic = part[1]
                plain_text = part[2]

                if tag_content_square_bracket:
                    text_segments_to_translate.append(tag_content_square_bracket[1:-1]) # 提取 [] 标签内的文本
                    line_segments.append({'type': 'square_bracket', 'original_tag': tag_content_square_bracket}) # 保存类型和原始标签
                    original_line_parts.append(tag_content_square_bracket) # 添加到原始行片段
                elif tag_content_italic:
                    text_segments_to_translate.append(tag_content_italic[3:-4]) # 提取 <i> 标签内的文本
                    line_segments.append({'type': 'italic', 'original_tag': tag_content_italic}) # 保存类型和原始标签
                    original_line_parts.append(tag_content_italic) # 添加到原始行片段
                elif plain_text:
                    text_segments_to_translate.append(plain_text) # 提取纯文本
                    line_segments.append({'type': 'plain'}) # 保存类型
                    original_line_parts.append(plain_text) # 添加到原始行片段
            original_segments_structure.append(line_segments) # 保存当前行的分段结构
            line.original_text = "".join(original_line_parts) # 保存原始行文本到line对象

        # 2. 批量翻译提取出的文本
        translated_segments = await translate_text_bulk(text_segments_to_translate, target_language)
        translated_segments_iterator = iter(translated_segments) # 创建迭代器

        # 3. 将翻译后的文本放回字幕行，并构建双语字幕
        for i, line in enumerate(subs):
            translated_line_parts = [] # 用于构建翻译后的字幕行文本
            for segment_info in original_segments_structure[i]:
                segment_type = segment_info['type']
                if segment_type == 'square_bracket':
                    translated_text = next(translated_segments_iterator) # 获取下一个翻译文本
                    translated_line_parts.append(f"[{translated_text}]") # 重新包裹 [] 标签
                elif segment_type == 'italic':
                    translated_text = next(translated_segments_iterator) # 获取下一个翻译文本
                    translated_line_parts.append(f"<i>{translated_text}</i>") # 重新包裹 <i> 标签
                elif segment_type == 'plain':
                    translated_text = next(translated_segments_iterator) # 获取下一个翻译文本
                    translated_line_parts.append(translated_text) # 直接添加纯文本
            translated_text_line = "".join(translated_line_parts) # 构建翻译后的字幕行文本
            # 构建双语字幕行：原始文本 + 换行符 + 翻译文本
            line.text = line.original_text + "\n" + translated_text_line

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

    response = HttpResponse(converted_subtitle, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{response_filename}"'

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