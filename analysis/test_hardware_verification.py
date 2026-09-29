"""Offline fault-injection tests for strict evidence validation and comparison."""
import csv
from copy import deepcopy
import pytest
from analysis.plot_hardware_verification import COLUMNS, FIELDS, compare, reference, validate_csv


def write_csv(path, rows, columns=COLUMNS):
    with path.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)


@pytest.fixture
def rows():
    return [[r[f] for f in COLUMNS] for r in reference()]


def test_reference_contract_and_zero_error(tmp_path, rows):
    path = tmp_path/'capture.csv'
    write_csv(path, rows)
    hardware = validate_csv(path)
    result = compare(hardware, reference())
    assert result['exact_pass']
    assert rows[0] == [0, 8191, 0, 1, 1, 0]
    assert result['records_with_any_mismatch'] == 0
    assert result['max_absolute_error'] == {'I': 0, 'Q': 0}
    assert result['rms_error'] == {'I': 0, 'Q': 0}


@pytest.mark.parametrize('fault', ['columns','missing','extra','duplicate','reorder','range_I',
                                  'range_Q','valid','start','end','fraction','missing_cell','extra_cell'])
def test_malformed_input_rejected(tmp_path, rows, fault):
    columns = COLUMNS.copy()
    if fault == 'columns': columns[1] = 'i'
    elif fault == 'missing': rows.pop()
    elif fault == 'extra': rows.append(rows[-1])
    elif fault == 'duplicate': rows[5][0] = 4
    elif fault == 'reorder': rows[4], rows[5] = rows[5], rows[4]
    elif fault == 'range_I': rows[5][1] = 8192
    elif fault == 'range_Q': rows[5][2] = -8193
    elif fault == 'valid': rows[5][3] = 2
    elif fault == 'start': rows[5][4] = -1
    elif fault == 'end': rows[5][5] = 2
    elif fault == 'fraction': rows[5][1] = '1.5'
    elif fault == 'missing_cell': rows[5].pop()
    elif fault == 'extra_cell': rows[5].append(0)
    path = tmp_path/'bad.csv'
    write_csv(path, rows, columns)
    with pytest.raises(ValueError): validate_csv(path)


@pytest.mark.parametrize('field', FIELDS)
def test_each_mismatch_fails_and_reports_first(field):
    expected = reference()
    hardware = deepcopy(expected)
    hardware[7][field] = expected[7][field] + 1 if field in ('I', 'Q') else 1-expected[7][field]
    result = compare(hardware, expected)
    assert not result['exact_pass']
    assert result['records_with_any_mismatch'] == 1
    assert result['mismatch_counts'] == {f: int(f == field) for f in FIELDS}
    assert result['first_mismatch_index'][field] == 7
    mismatch = result['first_eight_mismatches_per_field'][field][0]
    assert mismatch['difference'] == hardware[7][field]-expected[7][field]
    if field in ('I', 'Q'):
        assert result['max_absolute_error'][field] == 1
        assert result['rms_error'][field] == 1/32


def test_shift_is_not_silently_corrected():
    expected = reference()
    hardware = deepcopy(expected[1:]+expected[:1])
    for k, row in enumerate(hardware): row['index'] = k
    result = compare(hardware, expected)
    assert not result['exact_pass']
    assert result['mismatch_counts']['I'] > 900
    assert result['first_mismatch_index']['chirp_start'] == 0


def test_large_failure_is_bounded():
    expected = reference()
    hardware = deepcopy(expected)
    for row in hardware: row['I'] += 1
    result = compare(hardware, expected)
    assert result['mismatch_counts']['I'] == 1024
    assert len(result['first_eight_mismatches_per_field']['I']) == 8
    assert result['rms_error']['I'] == 1


def test_manifest_rejects_changed_evidence(tmp_path, monkeypatch):
    import analysis.plot_hardware_verification as module
    monkeypatch.setattr(module, 'OUT', tmp_path)
    evidence = tmp_path/'capture_1024.csv'
    evidence.write_text('original\n')
    manifest = module.preserve_evidence()
    assert module.preserve_evidence() == manifest
    evidence.write_text('changed\n')
    with pytest.raises(ValueError, match='differs'):
        module.preserve_evidence()


def test_raw_csv_disagreement_is_detected(tmp_path, monkeypatch):
    import analysis.plot_hardware_verification as module
    rows = reference()
    payload = b'RFC1\x01\x01\x00\x04\x04\x0e' + bytes(6)
    for r in rows:
        word = (r['I'] & 16383) | ((r['Q'] & 16383) << 14) | (r['valid'] << 28) | (r['chirp_start'] << 29) | (r['chirp_end'] << 30)
        payload += word.to_bytes(4, 'little')
    (tmp_path/'capture_1024.bin').write_bytes(payload)
    monkeypatch.setattr(module, 'OUT', tmp_path)
    assert module.raw_crosscheck(rows)['status'] == 'PASS'
    rows[17]['Q'] += 1
    result = module.raw_crosscheck(rows)
    assert result['status'] == 'FAIL'
    assert result['records_with_any_mismatch'] == 1
    assert result['first_eight_mismatches'][0]['index'] == 17


def test_public_physical_evidence_exact_match():
    """Pin real evidence and compare it with the independent model and decoder."""
    from analysis.plot_hardware_verification import ROOT, fingerprint, raw_crosscheck
    source = ROOT / 'examples/physical_capture'
    hashes = {
        'capture_1024.csv': '838cea308f4670e01a06aa13fcae285304edb8e953b948e3c67764cd3843ff76',
        'capture_1024.bin': '01588b97134f0fd15e7bb73dc4164e59adc20ae0d983de08ec3899d860910d8c',
    }
    for name, expected in hashes.items():
        assert fingerprint(source / name)['sha256'] == expected
    hardware = validate_csv(source / 'capture_1024.csv')
    assert compare(hardware, reference())['exact_pass']
    assert raw_crosscheck(hardware, source)['status'] == 'PASS'
