# fpga-utils Readme

For more information and updates:
http://alexforencich.com/wiki/en/projects/fpga-utils/start

GitHub repository:
https://github.com/alexforencich/fpga-utils

## Introduction

fpga-utils is a collection of utilities for working with FPGAs.

## ucf-insert-io.py

ucf-insert-io.py is used to add bank and IO comments to UCF files.  It reads
pinout definition files from Xilinx to fill in the information based on the
LOC constraint.  

For example, UCF lines like this:

    NET "clk"          LOC = "L8"  | IOSTANDARD=LVCMOS33;
    NET "clk"          LOC = "L8"  | IOSTANDARD=LVCMOS33; # (GCLK)
    NET "clk"          LOC = "L8"  | IOSTANDARD=LVCMOS33; # Bank = ?, IO_? (GCLK)

run through ucf-insert-io.py like so:

    ./ucf-insert-io.py -p s3e_ft256_pinout.csv --ioc 8 -u input.ucf -o output.ucf

will be converted to:

    NET "clk"          LOC = "L8"  | IOSTANDARD=LVCMOS33; # Bank = 2, IO_L09N_2/D6/GCLK13
    NET "clk"          LOC = "L8"  | IOSTANDARD=LVCMOS33; # Bank = 2, IO_L09N_2/D6/GCLK13 (GCLK)
    NET "clk"          LOC = "L8"  | IOSTANDARD=LVCMOS33; # Bank = 2, IO_L09N_2/D6/GCLK13 (GCLK)

The script is not guaranteed to be perfect so the output may require cleanup,
but it saves a great deal of time looking up each pin individually.  


