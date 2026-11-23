"""Customer-facing language only; no changes to crystallographic processing."""
import json
from pathlib import Path

LANGUAGES = ('zh-CN', 'en')

def selected(language=None):
    if language is None:
        path = Path(__file__).resolve().parent.parent / 'language.json'
        language = json.loads(path.read_text('utf-8-sig'))['default_language'] if path.exists() else 'zh-CN'
    if language not in LANGUAGES:
        raise ValueError('Supported interface languages: zh-CN, en')
    return language

def message(text, language):
    """Translate known intake notices; preserve original technical diagnostics."""
    if selected(language) != 'en':
        return text
    translations = {
        '数据目录未提供': 'The specimen data directory is missing.',
        '找不到数据文件夹，请检查路径；无需重新填写其他信息。': 'The data directory was not found. Correct its path; keep the other answers.',
        '尺寸未包含长度数值；不清楚可留空。': 'No dimension values were supplied. Leave unknown dimensions blank.',
        '尺寸请填三个长度，例如 0.050 × 0.052 × 0.054 mm；不清楚可留空。': 'Enter three lengths, for example 0.050 × 0.052 × 0.054 mm; leave unknown dimensions blank.',
        '尺寸请填三个正数，单位 mm，例如 0.050 × 0.052 × 0.054；不要填体积或其他单位。': 'Enter three positive lengths in mm, for example 0.050 × 0.052 × 0.054; do not enter a volume or another unit.',
        '温度单位只能为 K 或 C': 'Temperature units must be K or C.',
        '温度必须大于绝对零度': 'Temperature must be above absolute zero.',
    }
    if text.startswith('元素范围未明确：'):
        return 'Possible elements are not specified: ' + text.split('：', 1)[1]
    return translations.get(text, text)
