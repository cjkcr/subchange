from django.shortcuts import render
from django.http import HttpResponse
import pysubs2
import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

def subtitle_convert(request):
    if request.method == 'POST' and request.FILES['subtitle']:
        # 获取上传的文件
        subtitle_file = request.FILES['subtitle']
        subtitle_format = request.POST['format']
        custom_filename = request.POST.get('custom_filename', 'converted')

        # 保存上传的文件到临时路径
        temp_path = default_storage.save(subtitle_file.name, ContentFile(subtitle_file.read()))

        # 加载字幕
        subs = pysubs2.load(temp_path)

        # 自定义文件名
        response_filename = f"{custom_filename}.{subtitle_format}"

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
        os.remove(temp_path)
        os.remove(converted_file_path)

        return response
    return render(request, 'converter/upload.html')
