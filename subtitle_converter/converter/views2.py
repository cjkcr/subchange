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

async def translate_text(text, target_language):
    """
    使用 googletrans 将字幕文本翻译为目标语言，并保留格式标签。
    返回原始文本和翻译后的文本。
    """
    translator = Translator()
    try:
        # 使用正则表达式查找 [] 和 <i> 标签内的文本以及标签外的文本
        parts = re.findall(r'(\[.*?\])|(<i>.*?</i>)|([^\[\<]+)', text)
        translated_parts = []
        original_parts = [] # 用于存储原始文本部分

        for part in parts:
            tag_content_square_bracket = part[0]
            tag_content_italic = part[1]
            plain_text = part[2]

            if tag_content_square_bracket:
                # 翻译 [] 标签内的文本，并保留 [] 标签
                translated_content = await translator.translate(tag_content_square_bracket[1:-1], dest=target_language)
                translated_parts.append(f"[{translated_content.text}]")
                original_parts.append(tag_content_square_bracket) # 保留原始标签
            elif tag_content_italic:
                # 翻译 <i> 标签内的文本，并保留 <i> 标签
                translated_content = await translator.translate(tag_content_italic[3:-4], dest=target_language)
                translated_parts.append(f"<i>{translated_content.text}</i>")
                original_parts.append(tag_content_italic) # 保留原始标签
            elif plain_text:
                # 翻译纯文本内容
                translated_content = await translator.translate(plain_text, dest=target_language)
                translated_parts.append(translated_content.text)
                original_parts.append(plain_text) # 保留原始文本

        # 将原始文本各部分重新组合
        original_text = "".join(original_parts)
        # 将翻译后的各部分重新组合
        translated_text = "".join(translated_parts)

        return original_text, translated_text # 返回原始文本和翻译后的文本

    except Exception as e:
        # 如果翻译失败，返回原文
        print(f"Translation error: {e}")
        return text, text # 发生错误时，原始和翻译文本返回相同内容


async def subtitle_convert_and_download(subs, subtitle_format, response_filename, target_language):
    """
    将字幕转换为指定格式并提供下载，同时生成双语字幕。
    :param subs: pysubs2 字幕对象
    :param subtitle_format: 用户选择的输出格式 (srt, ass, ssa, vtt, sub)
    :param response_filename: 转换后的字幕文件名
    :param target_language: 用户选择的目标语言（如 'en'，'zh' 等）
    :return: HttpResponse 对象，包含转换后的文件内容
    """
    # 如果目标语言不是"无翻译"，则进行翻译
    if target_language != 'none':
        # 遍历所有字幕行进行翻译
        for line in subs:
            # 调用修改后的翻译函数翻译文本，获取原始文本和翻译文本
            original_text, translated_text = await translate_text(str(line.text), target_language)
            print(f"原文{original_text}")
            print(f"译文{translated_text}")
            # 将字幕行的文本设置为双语字幕格式，原始文本和翻译文本用换行符分隔
            line.text = original_text + "\n" + translated_text

    # 临时保存转换后的文件路径
    converted_file_path = f"/tmp/{response_filename}"

    # 根据选择的格式保存文件
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

    # 读取转换后的文件
    with open(converted_file_path, 'rb') as f:
        converted_subtitle = f.read()

    # 准备下载文件
    response = HttpResponse(converted_subtitle, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{response_filename}"'

    # 删除临时文件
    os.remove(converted_file_path)

    return response


async def subtitle_convert(request):
    if request.method == 'POST' and request.FILES['subtitle']:
        # 获取上传的文件
        subtitle_file = request.FILES['subtitle']
        subtitle_format = request.POST['format']
        target_language = request.POST['target_language']
        # 获取自定义文件名，如果没有提供就使用原文件名
        custom_filename = request.POST.get('custom_filename', 'converted')
        if not custom_filename:
            custom_filename = os.path.splitext(subtitle_file.name)[0]  # 使用上传文件的原始文件名（去除扩展名）

        # 保存上传的文件到临时路径
        temp_path = default_storage.save(subtitle_file.name, ContentFile(subtitle_file.read()))

        # 加载字幕
        subs = pysubs2.load(temp_path)

        # 调用转换和下载功能
        response = await subtitle_convert_and_download(subs, subtitle_format, f"{custom_filename}.{subtitle_format}", target_language)

        # 删除临时保存的文件
        default_storage.delete(temp_path)
        return response

    return render(request, 'converter/upload.html')