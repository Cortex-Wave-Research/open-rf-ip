"""Behavioral CSR specification. No RTL parsing or numerical waveform generation.

Transactions are indivisible state transitions; bus latency belongs to the adapter.
The caller supplies pre-edge busy/completion and consumes a one-edge start event.
"""
from models.python import control_registers as R
MASK = (1 << 32)-1
SHADOW = tuple(a for a,t in R.ACCESS.items() if t == 'SHADOW')

class ControlPlane:
    def __init__(self, high_purity=False, engine_kind=1):
        self.hp = bool(high_purity)
        self.kind = engine_kind
        self.reset()

    def reset(self):
        self.shadow = dict.fromkeys(SHADOW,0)
        self.shadow[R.ADDR_MODE] = self.kind
        self.active = dict.fromkeys(SHADOW,0)
        self.scratch = self.errors = self.sequence = 0
        self.dirty = self.valid = self.run = self.done = self.start = False

    @property
    def capabilities(self):
        return (R.CAP_HIGH_PURITY if self.hp else R.CAP_COMPACT) | R.CAP_PAUSE | (
            R.CAP_CHIRP | R.CAP_REPEAT if self.kind else R.CAP_TONE)

    def pair(self, low, active=False):
        bank = self.active if active else self.shadow
        return bank[low] + (bank[low+4] << 32)

    def configuration_ok(self):
        s=self.shadow
        if s[R.ADDR_MODE] != self.kind or s[R.ADDR_CHIRP_CONFIG] not in (0,1): return False
        if self.kind and not s[R.ADDR_CHIRP_LENGTH]: return False
        if not self.hp:
            if s[R.ADDR_NCO_PHASE_INC_HI] or s[R.ADDR_CHIRP_START_HI]: return False
            signed = self.pair(R.ADDR_CHIRP_STEP_LO)
            if signed & (1<<63): signed -= 1<<64
            if not -(1<<31) <= signed < (1<<31): return False
        return True

    def status(self, busy=False):
        return (int(busy or self.start)*R.STATUS_BUSY | int(self.done)*R.STATUS_DONE_STICKY |
                int(bool(self.errors))*R.STATUS_ERROR_STICKY | int(self.dirty)*R.STATUS_CONFIG_DIRTY |
                int(self.valid)*R.STATUS_CONFIG_VALID | int(self.run)*R.STATUS_RUN_ENABLE)

    def tick(self, request=None, *, busy=False, completion=False, reset=False):
        if reset:
            self.reset(); return (0,False)
        busy = busy or self.start
        self.start = False
        data, fault = 0,False
        if request is not None:
            address,write,value,select = request
            mask=sum(255<<(8*i) for i in range(4) if select & (1<<i))
            access=R.ACCESS.get(address)
            fault=(access is None or (write and access=='RO') or
                   (write and address==R.ADDR_RUN_CONTROL and bool(value & mask & ~1)))
            if fault:
                self.errors |= R.ERR_ILLEGAL_BUS_ACCESS
            elif not write:
                data = {R.ADDR_IP_ID:R.IP_ID_VALUE,R.ADDR_ABI_VERSION:R.ABI_VERSION_VALUE,
                        R.ADDR_CAPABILITIES:self.capabilities,R.ADDR_SCRATCH:self.scratch,
                        R.ADDR_COMMAND:0,R.ADDR_STATUS:self.status(busy),R.ADDR_ERROR_STATUS:self.errors,
                        R.ADDR_CONFIG_SEQUENCE:self.sequence,R.ADDR_RUN_CONTROL:int(self.run),
                        **self.shadow}[address]
            elif access=='SHADOW':
                self.shadow[address] = (self.shadow[address] & ~mask) | (value & mask)
                self.dirty=True
            elif address==R.ADDR_SCRATCH:
                self.scratch = (self.scratch & ~mask) | (value & mask)
            elif address==R.ADDR_RUN_CONTROL:
                if select & 1:self.run=bool(value & 1)
            elif address==R.ADDR_COMMAND:
                errors=0
                if select!=15 or value not in (R.CMD_COMMIT,R.CMD_START,R.CMD_CLEAR_STATUS):
                    errors=R.ERR_BAD_COMMAND
                elif value==R.CMD_CLEAR_STATUS:
                    self.errors=0; self.done=False
                elif value==R.CMD_COMMIT:
                    if busy:errors |= R.ERR_COMMIT_WHILE_BUSY
                    if not self.configuration_ok():errors |= R.ERR_INVALID_CONFIGURATION
                    if not errors:
                        self.active=self.shadow.copy();self.dirty=False;self.valid=True
                        self.sequence=(self.sequence+1)&MASK
                else:
                    if not self.kind: errors |= R.ERR_BAD_COMMAND
                    if busy: errors |= R.ERR_START_WHILE_BUSY
                    if self.dirty: errors |= R.ERR_START_WITH_DIRTY_CONFIG
                    if not self.valid: errors |= R.ERR_START_WITHOUT_VALID_CONFIG
                    if not self.run: errors |= R.ERR_START_WHILE_DISABLED
                    self.start = not errors
                self.errors |= errors
        if completion and self.kind:self.done=True
        return data,fault
