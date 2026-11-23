"""checkCIF identifiers used in both PDF parsing and diagnosis."""
import re

ALERT_TOKEN = re.compile(r'(?<![A-Z0-9_])([A-Z][A-Z0-9]*(?:_[0-9]+)?|[0-9]{3})_ALERT_([0-9])_([ABCG])(?![A-Z0-9_])', re.I)


def test_code(name):
    name = name.upper()
    return name[4:] if re.fullmatch(r'PLAT[0-9]{3}',name) else name.replace('_','')
