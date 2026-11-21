"""Offline tests of scientific-paper/scripts/check_dois.py (the network is mocked).

  python -m unittest discover -s tests
"""

import io
import os
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scientific-paper', 'scripts'))
import check_dois  # noqa: E402

# Shapes taken from api.crossref.org records (trimmed). The retracted one follows the record of
# 10.1016/S0140-6736(97)11096-0, whose `updated-by` holds a correction and a retraction from Retraction Watch.
RECORDS = {
	'10.1016/s0022-1694(97)00125-x': {'message': {
		'title': ['A modified Mann-Kendall trend test for autocorrelated data'],
		'author': [{'family': 'Hamed', 'given': 'Khaled H.'}, {'family': 'Rao', 'given': 'A. Ramachandra'}],
		'issued': {'date-parts': [[1998, 1]]}, 'container-title': ['Journal of Hydrology'], 'type': 'journal-article'}},
	'10.1016/s0140-6736(97)11096-0': {'message': {
		'title': ['RETRACTED: Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and pervasive developmental '
		          'disorder in children'],
		'author': [{'family': 'Wakefield', 'given': 'A.J.'}],
		'issued': {'date-parts': [[1998, 2]]}, 'container-title': ['The Lancet'], 'type': 'journal-article',
		'updated-by': [
			{'type': 'correction', 'label': 'Correction', 'source': 'retraction-watch',
			 'DOI': '10.1016/s0140-6736(04)15715-2'},
			{'type': 'retraction', 'label': 'Retraction', 'source': 'retraction-watch',
			 'DOI': '10.1016/s0140-6736(10)60175-4'}]}},
	'10.9999/retracted.no.prefix': {'message': {
		'title': ['A normal looking title'], 'author': [], 'issued': {'date-parts': [[2020]]},
		'updated-by': [{'type': 'retraction', 'DOI': '10.9999/notice'}]}},
	'10.9999/notice': {'message': {
		'title': ['Retraction notice'], 'author': [], 'issued': {'date-parts': [[2021]]},
		'update-to': [{'type': 'retraction', 'DOI': '10.9999/retracted.no.prefix'}]}},
	'10.9999/concern': {'message': {
		'title': ['Under concern'], 'author': [], 'issued': {'date-parts': [[2022]]},
		'updated-by': [{'type': 'expression_of_concern', 'DOI': '10.9999/eoc'}]}},
}


def fake_get(url):
	doi = url.split('/works/', 1)[-1] if '/works/' in url else None
	if doi is not None:
		doi = check_dois.urllib.parse.unquote(doi).lower()
		if doi in RECORDS:
			return RECORDS[doi]
	raise urllib.error.HTTPError(url, 404, 'Not Found', {}, None)


@mock.patch.object(check_dois, '_get', side_effect=fake_get)
class TestRetraction(unittest.TestCase):

	def test_clean_paper(self, _):
		_, info = check_dois.check('10.1016/S0022-1694(97)00125-X')
		self.assertFalse(info['retracted'])
		self.assertEqual(info['year'], 1998)

	def test_retracted_via_updated_by(self, _):
		_, info = check_dois.check('https://doi.org/10.1016/S0140-6736(97)11096-0')
		self.assertTrue(info['retracted'])

	def test_retracted_without_title_prefix(self, _):
		_, info = check_dois.check('10.9999/retracted.no.prefix')
		self.assertTrue(info['retracted'])

	def test_notice_is_not_the_work(self, _):
		_, info = check_dois.check('10.9999/notice')
		self.assertTrue(info['is_notice'])
		self.assertFalse(info['retracted'])

	def test_expression_of_concern_is_a_warning(self, _):
		_, info = check_dois.check('10.9999/concern')
		self.assertTrue(info['concern'])
		self.assertFalse(info['retracted'])

	def test_unknown_doi(self, _):
		self.assertIsNone(check_dois.check('10.9999/does-not-exist')[1])


BIB = r'''
@comment{ignored}
@article{hamed1998modified,
  title = {A modified {Mann-Kendall} trend test for autocorrelated data},
  author = {Hamed, Khaled H. and Rao, A. Ramachandra},
  year = {1998},
  doi = {10.1016/S0022-1694(97)00125-X}
}
@article{wrongtitle,
  title = "Trends in Mediterranean NDVI",
  year = 1998,
  doi = {10.1016/S0022-1694(97)00125-X}
}
@article{wrongyear,
  title = {A modified Mann-Kendall trend test for autocorrelated data},
  year = {2005},
  doi = {10.1016/S0022-1694(97)00125-X}
}
@article{retracted,
  title = {Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and pervasive developmental disorder in children},
  year = {1998},
  doi = {10.1016/S0140-6736(97)11096-0}
}
@book{nodoi, title = {No DOI here}, year = {2000}}
'''


@mock.patch.object(check_dois, '_get', side_effect=fake_get)
class TestBib(unittest.TestCase):

	def setUp(self):
		fd, self.path = tempfile.mkstemp(suffix='.bib')
		with os.fdopen(fd, 'w', encoding='utf-8') as f:
			f.write(BIB)

	def tearDown(self):
		os.remove(self.path)

	def test_parse(self, _):
		entries = check_dois.bib_entries(self.path)
		self.assertEqual([e[0] for e in entries], ['hamed1998modified', 'wrongtitle', 'wrongyear', 'retracted'])
		self.assertEqual(entries[0][2], 'A modified {Mann-Kendall} trend test for autocorrelated data')
		self.assertEqual(entries[1][3], '1998')

	def test_main_flags_the_bad_entries(self, _):
		out = io.StringIO()
		with mock.patch.object(sys, 'argv', ['check_dois.py', '--bib', self.path]), redirect_stdout(out):
			status = check_dois.main()
		text = out.getvalue()
		self.assertEqual(status, 1)
		self.assertIn('OK    hamed1998modified', text)
		self.assertIn('FAIL  wrongtitle', text)
		self.assertIn('title differs', text)
		self.assertIn('FAIL  wrongyear', text)
		self.assertIn('year differs', text)
		self.assertIn('FAIL  retracted', text)
		self.assertIn('RETRACTED or WITHDRAWN', text)
		self.assertIn('4 checked, 3 failed', text)

	def test_retracted_title_still_matches_without_prefix(self, _):
		# the bib title has no "RETRACTED:" prefix; the failure must be the retraction, not the title
		out = io.StringIO()
		with mock.patch.object(sys, 'argv', ['check_dois.py', '--bib', self.path]), redirect_stdout(out):
			check_dois.main()
		block = out.getvalue().split('FAIL  retracted', 1)[1]
		self.assertNotIn('title differs', block.split('\n\n')[0])


if __name__ == '__main__':
	unittest.main()
