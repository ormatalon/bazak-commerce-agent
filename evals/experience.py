"""Validate the frozen experience pilot without keys, network, or model calls."""

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

PILOT = Path(__file__).resolve().parent.parent / 'datasets/experience'


def load_pilot(directory: Path = PILOT) -> tuple[dict, list[dict]]:
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    for filename, expected in manifest['sha256'].items():
        # Git may change LF to CRLF on Windows; hash the same UTF-8 text on both.
        if hashlib.sha256((directory / filename).read_text(encoding='utf-8').encode('utf-8')).hexdigest() != expected:
            raise ValueError(f'Pilot snapshot changed: {filename}')
    cases = [json.loads(line) for filename in manifest['case_files']
             for line in (directory / filename).read_text(encoding='utf-8').splitlines() if line.strip()]
    if len(cases) != manifest['case_count'] or len({case['id'] for case in cases}) != len(cases):
        raise ValueError('Incorrect pilot count or duplicate case identity')
    if dict(Counter(case['language'] for case in cases)) != manifest['language_counts']:
        raise ValueError('Pilot language counts differ from the manifest')
    catalog = {p['id']: p for p in json.loads((directory / 'catalog.json').read_text(encoding='utf-8'))['products']}
    rates = json.loads((directory / 'exchange_rates.json').read_text(encoding='utf-8'))['units_per_usd']
    rubric = json.loads((directory / 'rubric.json').read_text(encoding='utf-8'))
    if rubric['review_status'] != 'assistant_draft':
        raise ValueError('Record explicit human review provenance before changing rubric status')
    for case in cases:
        turns = case['turns']
        if not turns or not all(isinstance(text, str) and text.strip() for text in turns):
            raise ValueError(f"Invalid conversation: {case['id']}")
        has_hebrew = any('\u0590' <= char <= '\u05ff' for text in turns for char in text)
        if has_hebrew != (case['language'] == 'he'):
            raise ValueError(f"Wrong language file: {case['id']}")
        expected = case['expected']
        if expected['answerability'] not in {'supported', 'supported_with_uncertainty', 'no_exact_match'}:
            raise ValueError(f"Unknown answerability: {case['id']}")
        if not expected['requirements'] or not expected['communication']:
            raise ValueError(f"Missing behavioral or communication expectations: {case['id']}")
        examples = [item['id'] for item in expected['acceptable_examples']]
        forbidden = set(expected.get('forbidden_product_ids', []))
        evidence = expected.get('catalog_evidence_ids', [])
        if set(examples) & forbidden or any(identifier not in catalog for identifier in examples + list(forbidden) + evidence):
            raise ValueError(f"Invalid catalog evidence: {case['id']}")
        if expected['answerability'] == 'no_exact_match' and examples:
            raise ValueError(f"No-match control has positive examples: {case['id']}")
        if expected['answerability'] != 'no_exact_match' and not examples:
            raise ValueError(f"Supported case needs evidence: {case['id']}")
        limit = expected.get('price_limit')
        if limit:
            units = Decimal(1) if limit['currency'] == 'USD' else Decimal(rates[limit['currency']])
            budget = Decimal(str(limit['max'])) / units
            for identifier in examples:
                price = Decimal(str(catalog[identifier]['price']))
                if price > budget or (price == budget and not limit['inclusive']):
                    raise ValueError(f"Positive example exceeds the stated budget: {case['id']}")
        reference = expected.get('reference')
        if reference and (not 0 <= reference['turn_index'] < len(turns)-1 or reference['card_index'] < 0):
            raise ValueError(f"Invalid dynamic reference: {case['id']}")
    return manifest, cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=PILOT)
    args = parser.parse_args()
    manifest, cases = load_pilot(args.directory)
    print(json.dumps({'status': 'valid', 'cases': len(cases),
                      'languages': manifest['language_counts'],
                      'multi_turn': sum(len(case['turns']) > 1 for case in cases),
                      'no_match_controls': sum(case['expected']['answerability'] == 'no_exact_match' for case in cases),
                      'annotation_status': manifest['annotation_status'], 'model_calls': 0}, indent=2))


if __name__ == '__main__':
    main()
