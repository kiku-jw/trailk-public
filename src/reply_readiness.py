"""Conservative surface continuation signals, not semantic completion/ASR confidence."""
import re
HANGING=re.compile(r'(?:^|\s)(?:и|но|или|если|потому что|чтобы|который|которая|которые|кто|что|в|на|для|о|от|с|к|без|между|через|and|or|but|if|because|although|with|for|of|the|a|an)$',re.I)
def continuation_reason(text):
 text=text.strip()
 if not text:return 'empty'
 if re.search(r'[,;:—–\-/]$|\.\.\.$|…$',text):return 'open_clause'
 if any(text.count(a)>text.count(b) for a,b in [('(',')'),('[',']'),('{','}'),('«','»'),('“','”')]) or text.count('"')%2:return 'open_delimiter'
 if not re.search(r'[.!?][»”"\]\)]*$',text) and HANGING.search(text):return 'hanging_function_word'
 return None
