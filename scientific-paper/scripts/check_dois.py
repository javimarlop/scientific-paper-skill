"""Check DOIs against Crossref and print what each one is, so that it can be compared with what the paper cites.

  python check_dois.py 10.1016/j.rse.2017.06.031 10.5281/zenodo.1234567
  python check_dois.py --bib refs.bib          every entry of a BibTeX file with a doi = {...}

Exit status 1 if a DOI does not resolve, if it points to a retracted or withdrawn work, or (with --bib) if the title
or the year in the BibTeX entry does not match the one the DOI resolves to.

It only asks Crossref (api.crossref.org) and DataCite (api.datacite.org) for the public metadata of the DOI; nothing
else leaves the computer. A DOI that Crossref does not know (e.g. one of DataCite, like Zenodo's) is looked up at
DataCite.

Retractions: Crossref puts the notices that update a work (retraction, withdrawal, removal, expression of concern,
correction) in the field `updated-by` of that work, including the Retraction Watch records that Crossref has
distributed since 2023. (The field `update-to` is the other direction: it is on the notice, pointing at the work.)
DataCite has no equivalent, so a DataCite DOI is never flagged; a clean result is not proof, so for the key
references look at the publisher's page too.

Then READ the title, authors and year: a DOI that resolves to another paper is as wrong as one that does not resolve.
The automatic comparison with --bib catches gross mismatches, not a wrong paper by the same authors with a similar
title.
"""

import argparse
import difflib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

AGENT = 'scientific-paper-skill (doi check; https://github.com/javimarlop/scientific-paper-skill)'

# Notices in `updated-by` that mean the work should not be cited as valid.
RETRACTING = {'retraction', 'withdrawal', 'removal', 'partial_retraction'}
CONCERN = {'expression_of_concern'}

TITLE_THRESHOLD = 0.85  # similarity (0-1) between normalised titles below which --bib reports a mismatch


def _get(url):
	request = urllib.request.Request(url, headers={'User-Agent': AGENT, 'Accept': 'application/json'})
	with urllib.request.urlopen(request, timeout=30) as response:
		return json.load(response)


def _notices(m):
	"""Types of the notices that update this work (Crossref `updated-by`), lower case with underscores."""
	types = set()
	for u in m.get('updated-by', []) or []:
		t = (u.get('type') or u.get('label') or '').strip().lower().replace(' ', '_').replace('-', '_')
		if t:
			types.add(t)
	return types


def crossref(doi):
	m = _get('https://api.crossref.org/works/' + urllib.parse.quote(doi))['message']
	year = (m.get('issued', {}).get('date-parts') or [[None]])[0][0]
	names = ['%s %s' % (a.get('family', a.get('name', '?')), (a.get('given') or '')[:1]) for a in m.get('author', [])]
	title = (m.get('title') or ['?'])[0]
	notices = _notices(m)
	retracted = bool(notices & RETRACTING) or title.upper().startswith(('RETRACTED', 'WITHDRAWN'))
	return {'source': 'Crossref', 'title': title, 'authors': names, 'year': year,
	        'venue': (m.get('container-title') or [''])[0], 'type': m.get('type'),
	        'retracted': retracted, 'concern': bool(notices & CONCERN),
	        'is_notice': bool(m.get('update-to'))}


def datacite(doi):
	m = _get('https://api.datacite.org/dois/' + urllib.parse.quote(doi))['data']['attributes']
	names = [c.get('name', '?') for c in m.get('creators', [])]
	return {'source': 'DataCite', 'title': (m.get('titles') or [{}])[0].get('title', '?'), 'authors': names,
	        'year': m.get('publicationYear'), 'venue': m.get('publisher') or '',
	        'type': (m.get('types') or {}).get('resourceTypeGeneral'), 'retracted': False, 'concern': False,
	        'is_notice': False}


def check(doi):
	doi = normalise_doi(doi)
	for lookup in (crossref, datacite):
		try:
			return doi, lookup(doi)
		except (urllib.error.HTTPError, KeyError):
			continue
		except urllib.error.URLError as error:
			return doi, {'error': 'no network: %s' % error.reason}
	return doi, None


def normalise_doi(doi):
	return re.sub(r'^(https?://(dx\.)?doi\.org/|doi:)', '', doi.strip(), flags=re.I)


# --- BibTeX -----------------------------------------------------------------------------------------------------

def _field(body, name):
	"""Value of a BibTeX field, with nested braces, or None."""
	m = re.search(r'(?<![\w-])' + name + r'\s*=\s*', body, flags=re.I)
	if not m:
		return None
	i = m.end()
	if i >= len(body):
		return None
	if body[i] == '{':
		depth, j = 0, i
		while j < len(body):
			if body[j] == '{':
				depth += 1
			elif body[j] == '}':
				depth -= 1
				if depth == 0:
					return body[i + 1:j]
			j += 1
		return None
	if body[i] == '"':
		j = body.find('"', i + 1)
		return body[i + 1:j] if j > i else None
	m = re.match(r'[^,}\s]+', body[i:])
	return m.group(0) if m else None


def bib_entries(path):
	"""[(key, doi, title, year)] for every entry with a doi field."""
	with open(path, encoding='utf-8') as f:
		text = f.read()
	entries = []
	for chunk in re.split(r'(?m)^\s*@', text)[1:]:
		head = re.match(r'\s*(\w+)\s*[{(]\s*([^,\s]*)\s*,', chunk)
		if not head or head.group(1).lower() in ('comment', 'string', 'preamble'):
			continue
		doi = _field(chunk, 'doi')
		if doi:
			year = _field(chunk, 'year') or (_field(chunk, 'date') or '')[:4] or None
			entries.append((head.group(2), doi.strip(), _field(chunk, 'title'), year))
	return entries


def _norm_title(title):
	title = re.sub(r'\\[a-zA-Z]+\s*', ' ', title or '')  # LaTeX commands
	title = re.sub(r'<[^>]+>', ' ', title)                 # JATS/HTML tags in Crossref titles
	title = re.sub(r'[^\w\s]', ' ', title.lower())
	return ' '.join(title.split())


def compare(entry_title, entry_year, info):
	"""List of mismatches between a BibTeX entry and the metadata of its DOI."""
	problems = []
	if entry_title:
		ratio = difflib.SequenceMatcher(None, _norm_title(entry_title), _norm_title(info['title'])).ratio()
		if ratio < TITLE_THRESHOLD:
			problems.append('title differs (similarity %.2f): bib "%s"' % (ratio, ' '.join(entry_title.split())))
	if entry_year and info.get('year'):
		try:
			if abs(int(str(entry_year)[:4]) - int(info['year'])) > 1:  # online-first vs issue year: allow 1
				problems.append('year differs: bib %s' % entry_year)
		except ValueError:
			problems.append('year not a number in bib: %s' % entry_year)
	return problems


# --- main -------------------------------------------------------------------------------------------------------

def main():
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument('dois', nargs='*')
	parser.add_argument('--bib', help='a BibTeX file: every entry with a doi field, compared by title and year')
	args = parser.parse_args()
	items = [(None, d, None, None) for d in args.dois] + (bib_entries(args.bib) if args.bib else [])
	if not items:
		parser.error('give DOIs or --bib')
	bad = 0
	for key, d, entry_title, entry_year in items:
		doi, info = check(d)
		label = '%s  ' % key if key else ''
		if not info or 'error' in info:
			bad += 1
			print('FAIL  %s%s  %s' % (label, doi, info['error'] if info else 'does not resolve (Crossref, DataCite)'))
			continue
		problems = compare(entry_title, entry_year, info) if key else []
		if info['retracted']:
			problems.insert(0, '*** RETRACTED or WITHDRAWN ***')
		if info['is_notice']:
			problems.insert(0, 'this DOI is a notice (correction or retraction), not the work itself')
		warn = ['expression of concern'] if info['concern'] else []
		bad += bool(problems)
		authors = ', '.join(info['authors'][:3]) + (' et al.' if len(info['authors']) > 3 else '')
		status = 'FAIL' if problems else ('WARN' if warn else 'OK  ')
		print('%s  %s%s  [%s]\n        %s (%s)\n        %s\n        %s' % (
			status, label, doi, info['source'], authors, info['year'], info['title'], info['venue']))
		for p in problems + warn:
			print('        ! %s' % p)
	print('\n%d checked, %d failed. Compare each title, author and year with the citation in the paper.' % (
		len(items), bad))
	return 1 if bad else 0


if __name__ == '__main__':
	sys.exit(main())
