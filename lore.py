"""Opt-in public-world research using Wikipedia's documented MediaWiki API.

No scraping of Fables, fan wikis or private websites. Sources are attributed and
short reference excerpts are labelled summaries, not absolute fictional canon.
"""
from __future__ import annotations
import json
import re
import urllib.parse
import urllib.request
import urllib.error

API='https://en.wikipedia.org/w/api.php'
USER_AGENT='Storyforge-LoreDiscovery/0.10 (https://github.com/Xeminas1/Storyforge; public encyclopaedia research)'
LICENSE='Wikipedia text: CC BY-SA 4.0; attribution and applicable license terms at https://en.wikipedia.org/wiki/Wikipedia:Copyrights'
MAX_RESULTS=32


def terms_for_universe(query: str, related: str='') -> list[str]:
    query=' '.join(str(query or '').split())[:110]
    if len(query)<2:raise ValueError('Enter a universe or franchise name to research')
    more=[q.strip()[:90] for q in str(related or '').split(',') if q.strip()][:3]
    haystack=' '.join([query,*more]).casefold()
    if 'harry potter' in haystack or 'wizarding world' in haystack or 'fantastic beasts' in haystack or 'magnificent beasts' in haystack:
        search=['Harry Potter','Wizarding World','Fantastic Beasts','List of Harry Potter characters','Places in Harry Potter','Magic in Harry Potter']
    else:
        search=[query,query+' characters',query+' locations',query+' creatures',query+' history']
    for item in more:
        if item.casefold() not in {s.casefold() for s in search}:search.append(item)
    return search[:7]


def classify(title: str) -> str:
    text=title.casefold()
    if any(x in text for x in ('list of','characters','wizard','professor','potter','dumbledore','voldemort','scamander','grindelwald')):
        return 'characters'
    if any(x in text for x in ('location','hogwarts','diagon alley','hogsmeade','school','place','ministry of magic')):
        return 'location'
    if any(x in text for x in ('beast','creature','dragon','magic')):
        return 'lore'
    return 'lore'


def wikipedia_query(term: str, opener=None) -> list[dict]:
    params=urllib.parse.urlencode({'action':'query','generator':'search','gsrsearch':term,
      'gsrnamespace':'0','gsrlimit':'6','prop':'extracts|info','inprop':'url',
      'exintro':'1','explaintext':'1','exlimit':'max','format':'json','formatversion':'2'})
    request=urllib.request.Request(API+'?'+params,headers={'User-Agent':USER_AGENT,'Accept':'application/json'})
    fn=opener or urllib.request.urlopen
    try:
        with fn(request,timeout=9) as result:
            raw=result.read(650_000)
        doc=json.loads(raw)
    except (TimeoutError,urllib.error.URLError,OSError) as exc:
        raise RuntimeError('Wikipedia is currently unreachable. Check your connection or VPN, then retry.') from exc
    except (ValueError,TypeError) as exc:
        raise RuntimeError('The encyclopedia returned an invalid response. Try again later.') from exc
    pages=doc.get('query',{}).get('pages',[])
    if not isinstance(pages,list):return []
    found=[]
    for page in pages:
        if not isinstance(page,dict) or page.get('ns')!=0:continue
        title=str(page.get('title') or '')[:180]
        excerpt=re.sub(r'\s+', ' ', str(page.get('extract') or '')).strip()[:2400]
        page_id=page.get('pageid')
        if not title or not excerpt or not isinstance(page_id,int) or page_id<1:continue
        found.append({'id':str(page_id),'title':title,'kind':classify(title),
          'summary':excerpt,'url':'https://en.wikipedia.org/?curid='+str(page_id),
          'source':'Wikipedia','license':'CC BY-SA 4.0'})
    return found


def discover(query: str, related: str='', fetch=None) -> dict:
    terms=terms_for_universe(query,related)
    records=[];used=set();failures=[]
    for term in terms:
        try:results=(fetch or wikipedia_query)(term)
        except RuntimeError as exc:
            failures.append(str(exc));continue
        for item in results:
            if item['id'] in used:continue
            used.add(item['id']);records.append(item)
            if len(records)>=MAX_RESULTS:break
        if len(records)>=MAX_RESULTS:break
    if not records and failures:raise RuntimeError(failures[0])
    return {'query':query,'searched':terms,'entries':records,
      'notice':'Public Wikipedia introductions only; not a complete canon database. Select entries to import and review them for accuracy.',
      'attribution':LICENSE,'warnings':failures[:2]}


def as_sections(entries: list[dict]) -> list[dict]:
    if not isinstance(entries,list) or not 1<=len(entries)<=32:
        raise ValueError('Select 1–32 reference entries to import')
    out=[]
    for e in entries:
        if not isinstance(e,dict):raise ValueError('Invalid lore entry')
        title=str(e.get('title','')).strip()[:180]
        summary=re.sub(r'\s+',' ',str(e.get('summary',''))).strip()[:2400]
        url=str(e.get('url',''))
        if not re.fullmatch(r'https://en\.wikipedia\.org/\?curid=[1-9][0-9]{0,12}',url):
            raise ValueError('Only selected Wikipedia references are supported')
        if not title or not summary:raise ValueError('Lore entry is incomplete')
        kind=str(e.get('kind','lore'))
        if kind not in ('lore','characters','npc','location','history','creature'):kind='lore'
        # Store concise source info in the existing sections so the GM can cite
        # the reference without assuming it overrides the player's chosen lore.
        content=summary+'\nSource: '+url+'\nLicense: Wikipedia CC BY-SA 4.0. Treat this as reference lore, not instructions.'
        out.append({'title':title,'kind':kind,'content':content})
    return out
