import pytest
from models.python.control_plane import ControlPlane,SHADOW
from models.python import control_registers as R

@pytest.mark.parametrize('hp',[False,True])
@pytest.mark.parametrize('kind',[0,1])
def test_state_contract(hp,kind):
    c=ControlPlane(hp,kind)
    def wr(a,v,sel=15,**kw):return c.tick((a,True,v,sel),**kw)
    assert not c.valid and not c.dirty and not c.run
    wr(R.ADDR_COMMAND,R.CMD_START)
    assert c.errors & R.ERR_START_WITHOUT_VALID_CONFIG
    wr(R.ADDR_COMMAND,R.CMD_CLEAR_STATUS)
    wr(R.ADDR_CHIRP_LENGTH,2)
    wr(R.ADDR_CHIRP_STEP_LO,0xffffffff);wr(R.ADDR_CHIRP_STEP_HI,0xffffffff)
    assert c.dirty and not any(c.active.values())
    wr(R.ADDR_COMMAND,R.CMD_COMMIT)
    assert c.valid and not c.dirty and c.sequence==1
    before=c.active.copy()
    wr(R.ADDR_NCO_PHASE_INC_LO,0x89abcdef)
    wr(R.ADDR_NCO_PHASE_INC_HI,0x12345678)
    assert c.active==before
    wr(R.ADDR_COMMAND,R.CMD_COMMIT,busy=True)
    assert c.active==before and c.errors & R.ERR_COMMIT_WHILE_BUSY
    wr(R.ADDR_COMMAND,R.CMD_COMMIT)
    assert (c.sequence==2)==hp
    if not hp:assert c.active==before and c.errors & R.ERR_INVALID_CONFIGURATION
    wr(R.ADDR_COMMAND,3)
    assert c.errors & R.ERR_BAD_COMMAND
    c.tick(reset=True)
    assert not c.valid and not c.dirty and c.sequence==0

@pytest.mark.parametrize('low,high,valid',[(0x7fffffff,0,True),(0x80000000,0xffffffff,True),(0x80000000,0,False),(1,0xffffffff,False)])
def test_signed_compact_validation(low,high,valid):
    c=ControlPlane(False,1)
    for a,v in [(R.ADDR_CHIRP_LENGTH,1),(R.ADDR_CHIRP_STEP_LO,low),(R.ADDR_CHIRP_STEP_HI,high)]:c.tick((a,True,v,15))
    assert c.configuration_ok()==valid

@pytest.mark.parametrize('reg',SHADOW)
def test_zero_select_marks_dirty_without_changing_bits(reg):
    c=ControlPlane(True)
    before=c.shadow.copy();c.tick((reg,True,0xffffffff,0))
    assert c.shadow==before and c.dirty

def test_completion_wins_clear_and_sequence_wrap():
    c=ControlPlane(True)
    c.tick((R.ADDR_COMMAND,True,R.CMD_CLEAR_STATUS,15),completion=True)
    assert c.done
    c.tick((R.ADDR_CHIRP_LENGTH,True,1,15));c.sequence=0xffffffff
    c.tick((R.ADDR_COMMAND,True,R.CMD_COMMIT,15));assert c.sequence==0
