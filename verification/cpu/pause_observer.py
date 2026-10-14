"""Pause checking uses pre-edge RUN_ENABLE, never firmware progress telemetry."""
def scope(handle, path):
    for component in path.split('.'):
        handle = handle[component]
    return handle


class PauseObserver:
    def __init__(self, controlled, hp, kind):
        path = 'high_purity.nco' if hp else ('compact.chirp.nco' if kind else 'compact.nco')
        self.nco = scope(controlled.engine, path)
        self.fields = [(self.nco,n) for n in ('phase','i_out','q_out')]
        if hp:
            self.fields += [(self.nco,n) for n in
                            ('q_read','i_read','q_sign','i_sign','q_peak','i_peak','pending_valid')]
        if kind:
            path = 'high_purity.controller' if hp else 'compact.chirp.controller'
            c = scope(controlled.engine,path)
            self.fields += [(c,n) for n in ('start_word','step_word','last_count','repeat_latched',
                                           'phase_increment','chirp_count','busy')]
            if hp:self.fields += [(c,n) for n in ('start_pending','end_pending')]
        self.hp = hp
        self.previous = None
        self.had_sample = False
        self.paused_cycles = 0
        self.in_pause = False
        self.resumed_samples = 0
        self.resume_cycle = None

    def check(self, cycle, reset, enable_before_edge, model, actual):
        state = [int(getattr(h,n).value) for h,n in self.fields]
        assert state[0] == model.phase, ('phase', cycle,state[0],model.phase)
        if self.hp:
            assert int(self.nco.pending_valid.value) == int(model.pending is not None)
        if not reset and not enable_before_edge:
            assert not any(actual[k] for k in ('valid','chirp_start','chirp_end'))
            assert state == self.previous, ('paused state changed',cycle,state,self.previous)
            if self.had_sample:
                self.paused_cycles += 1
                self.in_pause = True
        if not reset and enable_before_edge and self.in_pause:
            self.resume_cycle = cycle
            self.in_pause = False
        if self.resume_cycle is not None and actual['valid']:
            self.resumed_samples += 1
        self.had_sample |= bool(actual['valid'])
        self.previous = state
