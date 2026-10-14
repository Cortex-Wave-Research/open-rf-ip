"""ABI-level checks; successful write response data has no architectural meaning.

See docs/control_plane.md Bus protocol, and the frozen control_bus.Bus.access.
Adapter response wiring is separately covered by openrf_wb_formal.p_response_data.
"""
from models.python import control_registers as R


def completion(request, actual_request, cyc, stb, ack, err, rdata, expected):
    assert actual_request == request, ('Wishbone payload', actual_request, request)
    assert cyc == 1 and stb == 1, ('termination without request', cyc, stb)
    data, error = expected
    assert (ack, err) == (int(not error), int(error)), ('termination', ack, err, error)
    if not request[1] or error:
        assert rdata == (0 if error else data), ('read/error data', rdata, data, error)


def csr_state(csr, model):
    """Check side effects and isolation every edge, not only subsequent reads."""
    values = dict(scratch=model.scratch, errors=model.errors,
                  sequence_number=model.sequence, dirty=model.dirty,
                  done_sticky=model.done, run_enable_o=model.run,
                  config_valid_o=model.valid, start_o=model.start,
                  active_nco_o=model.pair(R.ADDR_NCO_PHASE_INC_LO, True),
                  active_start_o=model.pair(R.ADDR_CHIRP_START_LO, True),
                  active_step_o=model.pair(R.ADDR_CHIRP_STEP_LO, True),
                  active_length_o=model.active[R.ADDR_CHIRP_LENGTH],
                  active_repeat_o=model.active[R.ADDR_CHIRP_CONFIG] & 1)
    for name, expected in values.items():
        actual = int(getattr(csr, name).value)
        assert actual == expected, ('CSR state', name, actual, expected)
    for index, address in enumerate(model.shadow):
        actual = int(csr.shadow[index].value)
        assert actual == model.shadow[address], ('shadow', address, actual, model.shadow[address])
