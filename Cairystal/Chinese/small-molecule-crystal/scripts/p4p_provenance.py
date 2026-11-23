"""Reject reconstructed P4P as an independent experimental metadata source."""
import re

def require_experimental_p4p(text):
    if re.search(r'^\s*FILEID\s+.*(?:created|generated|exported)\s+by\s+OLEX2\b',text,re.I|re.M):
        raise ValueError('Reconstructed Olex2 P4P is not an original measurement record. '
                         '请使用原始仪器 P4P、同次实验的 cif_od / PCF 或实验记录；'
                         'Olex2 导出的 CSIZE 零值不能作为实测温度。')
