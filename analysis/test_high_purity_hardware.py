"""Offline evidence rejection and exact-comparison regression, no hardware."""
import copy
import csv
import json
from pathlib import Path
import pytest
from analysis import verify_high_purity_hardware as hp


def test_pinned_physical_evidence_exact():
    hp.check_evidence()
    rows=hp.validate_csv(hp.INPUT)
    expected=hp.reference(hp.configuration())
    result=hp.compact.compare(rows,expected)
    assert result['exact_pass'] and result['records_with_any_mismatch']==0
    assert hp.raw_crosscheck(rows,hp.INPUT.with_suffix('.bin'))['status']=='PASS'
    assert expected[0]==dict(index=0,I=131071,Q=0,valid=1,chirp_start=1,chirp_end=0)
    assert all(r['chirp_end']==0 for r in expected)


@pytest.mark.parametrize('fault',['header','short','duplicate','reorder','width','flag','fraction','extra'])
def test_malformed_rejected(tmp_path,fault):
    with hp.INPUT.open(newline='') as f: rows=list(csv.reader(f))
    if fault=='header':rows[0][1]='i'
    elif fault=='short':rows.pop()
    elif fault=='duplicate':rows[5][0]=rows[4][0]
    elif fault=='reorder':rows[5],rows[6]=rows[6],rows[5]
    elif fault=='width':rows[5][1]='131072'
    elif fault=='flag':rows[5][3]='2'
    elif fault=='fraction':rows[5][2]='1.5'
    elif fault=='extra':rows[5].append('0')
    path=tmp_path/'bad.csv'
    with path.open('w',newline='') as f:csv.writer(f).writerows(rows)
    with pytest.raises(ValueError):hp.validate_csv(path)


@pytest.mark.parametrize('field',hp.FIELDS)
def test_each_field_exact_no_tolerance(field):
    expected=hp.reference(hp.configuration());rows=copy.deepcopy(expected)
    rows[17][field]+=1
    r=hp.compact.compare(rows,expected)
    assert not r['exact_pass'] and r['records_with_any_mismatch']==1
    assert r['mismatch_counts'][field]==1 and r['first_mismatch_index'][field]==17


def test_no_silent_realignment():
    expected=hp.reference(hp.configuration())
    result=hp.compact.compare(expected[1:]+expected[:1],expected)
    assert not result['exact_pass'] and result['mismatch_counts']['I']>900


def test_hash_tampering_rejected(tmp_path):
    data=json.loads(hp.MANIFEST.read_text())
    data['evidence'][str(hp.INPUT.relative_to(hp.ROOT))]['sha256']='0'*64
    path=tmp_path/'manifest.json';path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='Immutable evidence changed'):hp.check_evidence(path)


def test_raw_csv_disagreement_and_absence(tmp_path):
    rows=hp.validate_csv(hp.INPUT);rows[99]['Q']+=1
    r=hp.raw_crosscheck(rows,hp.INPUT.with_suffix('.bin'))
    assert r['status']=='FAIL' and r['records_with_any_mismatch']==1
    assert hp.raw_crosscheck(rows,tmp_path/'missing.bin')['message']=='RAW RFC2 CROSS-CHECK: NOT AVAILABLE'


def test_reference_matches_closed_form():
    from models.python.high_purity import phase_to_iq
    cfg=hp.configuration()
    for k,row in enumerate(hp.reference(cfg)):
        phase=(k*cfg['start_word']+cfg['step']*k*(k-1)//2)%(1<<64)
        assert (row['I'],row['Q'])==phase_to_iq(phase)
