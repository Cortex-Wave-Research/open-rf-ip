"""Interpret data only in its protocol-valid window; None means not applicable."""


def resolved(handle):
    bits = handle.value
    assert bits.is_resolvable, ('required signal unresolved', handle._path, str(bits))
    return int(bits)


def request_payload(handle, address, write, data, mask):
    wr = bool(resolved(getattr(handle, write)))
    return (resolved(getattr(handle, address)), wr,
            resolved(getattr(handle, data)) if wr else None,
            resolved(getattr(handle, mask)))


class DBusObserver:
    def __init__(self):
        self.pending = None
        self.expected = None
        self.events = []
        self.reads = {}
        self.ignored_read_payloads = 0

    def check(self, d, cycle):
        if resolved(d.d_rsp_ready):
            assert self.pending is not None, ('unowned CPU read response', cycle)
            data, error = resolved(d.d_rdata), resolved(d.d_error)
            address = self.pending
            if address >> 16 == 0x4000:
                assert self.expected is not None, ('CPU response before WB completion', cycle)
                assert (data, error) == self.expected, ('CPU read response', cycle, data, error, self.expected)
            else:
                assert not error, ('local read error', cycle, address)
            self.reads[address] = data
            self.events.append([cycle, 'read_response', address, data, error])
            self.pending = self.expected = None
        if resolved(d.d_valid) and resolved(d.d_ready):
            request = request_payload(d, 'd_address','d_wr','d_data','d_mask')
            self.events.append([cycle, 'command', *request])
            if not request[1]:
                assert self.pending is None, ('overlapping CPU reads', cycle)
                self.pending = request[0]
                self.ignored_read_payloads += 1

    def wishbone(self, request, result):
        if not request[1]:
            assert self.pending == 0x40000000 + request[0]
            assert self.expected is None
            self.expected = (0 if result[1] else result[0], int(result[1]))
