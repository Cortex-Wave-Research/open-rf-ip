# Manual LIFCL-40-EVN programming and capture

Run from the repository root after the [offline tests and build](verification.md). The scripts do not automatically program the board. SRAM loading is temporary; power loss clears both configuration and captured RAM. No external flash write is required.

Use the board's normal power and programming USB connection. With power off, check JP2 shorted and JP1 open before powering up. The capture uses native 12 MHz clock and on-board FT2232H channel-B I²C connections. Use the serial of your own board in place of `BOARD_SERIAL` below.

An installed openFPGALoader with `crosslinknx_evn` / Nexus SRAM support is required. The original flow used openFPGALoader 0.13.1. `fpga/lifcl40/openfpgaloader_local.sh` is an optional launcher for packages extracted under `build/lifcl40/tools/openfpgaloader`; those local packages are not distributed. With a system installation, invoke `openFPGALoader` directly:

```sh
openFPGALoader -b crosslinknx_evn --ftdi-serial BOARD_SERIAL --write-sram build/lifcl40/capture_readback.bit
```

The operator must arrange appropriate USB permissions; the validated workstation used sudo for its local launcher. No fixed USB bus/device number is assumed. Expected capture LEDs are D3 ON (done), D4 OFF (no error).

For a new, supervised physical readback, install the optional host dependency and select a new output filename:

```sh
.venv/bin/python -m pip install pyftdi
.venv/bin/python fpga/lifcl40/capture/read_capture.py --url ftdi://ftdi:2232h:BOARD_SERIAL/2 --output reports/hardware_capture/new_capture.csv
```

Run programmer and reader sequentially. The reader uses channel B (`/2`) through libusb, not a tty device. It saves CSV and binary and refuses existing output names. Successful readback alone does not prove numerical correctness. Preserve the new files, record the exact configuration, and compare offline. Never overwrite the included example or original physical evidence.

For the already included evidence, no hardware or PyFtdi installation is needed:

```sh
.venv/bin/python analysis/plot_hardware_verification.py
```
