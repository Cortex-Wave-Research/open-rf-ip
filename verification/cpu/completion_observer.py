"""One-shot completion lifecycle, independent of the final sticky-bit value."""
from models.python import control_registers as R


class CompletionObserver:
    def __init__(self):
        self.events = {}
        self.status_reads = []
        self.cursor = 0

    def check(self, cycle, request, model, actual, busy, sample_count, dbus):
        for event in dbus[self.cursor:]:
            if event[1] == 'read_response' and event[2] == 0x40000000 + R.ADDR_STATUS:
                assert not event[4]
                self.status_reads.append([cycle, event[3]])
        self.cursor = len(dbus)
        if model.start:
            assert 'start' not in self.events, 'duplicate accepted chirp START'
            self.events['start'] = cycle
        if actual['valid'] and actual['chirp_end']:
            assert 'final_sample' not in self.events
            assert sample_count == 10000
            assert not model.done and busy
            self.events['final_sample'] = cycle
        if model.done and 'done_set' not in self.events:
            assert cycle == self.events['final_sample'] + 1 and not busy
            self.events['done_set'] = cycle
        clear = request == (R.ADDR_COMMAND, True, R.CMD_CLEAR_STATUS, 15)
        if clear and 'done_set' in self.events and 'clear' not in self.events:
            reads = [(c, s) for c, s in self.status_reads if
                     c > self.events['done_set'] and s & R.STATUS_DONE_STICKY and not s & R.STATUS_BUSY]
            # Firmware first exits the BUSY poll, then explicitly checks DONE.
            assert len(reads) >= 2, ('firmware did not observe completion before clear', reads)
            assert not model.done and not model.errors and not busy
            self.events.update(poll_observed=reads[0][0], done_observed=reads[1][0], clear=cycle)

    def validate(self, cycle, model, busy, transcript, final_pass=False):
        e = self.events
        assert e['start'] < e['final_sample'] < e['done_set'] < e['poll_observed'] < e['done_observed'] < e['clear'] < cycle
        assert any(row[0] == e['clear'] + 1 and row[1] == 'wb' and
                   row[2] == R.ADDR_COMMAND and row[3] and not row[6] for row in transcript)
        assert not model.done and not model.errors and not busy
        if final_pass:
            e['pass_mailbox'] = cycle
