#!/usr/bin/env python
"""
Inserts IO pin information into UCF files
"""

from __future__ import print_function

import argparse
import csv
import re
from jinja2 import Template

import verilogParse

def main():
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument('input',          type=str, help="input UCF file")
    parser.add_argument('-p', '--pkg',    type=str, help="Xilinx package file")
    parser.add_argument('--ioc',          type=int, help="IO name column (for multi-part CSV)")
    parser.add_argument('-o', '--output', type=str, help="output file name")

    args = parser.parse_args()

    pkg_name = args.pkg
    input_name = args.input
    output_name = args.output
    opt_io_col = -1 if args.ioc is None else args.ioc-1

    if pkg_name is None:
        raise Exception("No package file specified")
    if input_name is None:
        raise Exception("No input file specified")
    if output_name is None:
        output_name = input_name + '.out'
    
    print("Reading package file")
    
    try:
        pkg_file = open(pkg_name, 'r')
    except Exception as ex:
        print("Error opening \"%s\": %s" %(pkg_name, ex.strerror), file=sys.stderr)
        exit(1)
    
    pkg_contents = list()
    pin_col = -1
    bank_col = -1
    io_col = -1
    
    row_length = 0
    
    # read header
    header = next(pkg_file)
    
    if ',' in header:
        pkg_reader = csv.reader(pkg_file)
    else:
        pkg_reader = pkg_file
    
    for line in pkg_reader:
        if isinstance(line, str):
            row = line.split()
        else:
            row = line
        if len(row) > 1:
            row = [x.strip() for x in row]
            pkg_contents.append(row)
            
            # detect IO_ column
            if io_col < 0:
                for i in range(len(row)):
                    if "IO_" in row[i]:
                        if opt_io_col == i or opt_io_col < 0:
                            io_col = i
                        
                        # This should be a valid row, so get the length
                        row_length = len(row)
                        
                        # Detect pin and bank columns
                        for k in range(len(row)):
                            if re.match("[a-zA-Z]{1,2}[0-9]{1,2}", row[k]) is not None:
                                pin_col = k
                            if re.match("[0-9]{1,2}", row[k]) is not None:
                                bank_col = k
            
    
    # filter length
    pkg_contents = [x for x in pkg_contents if len(x) == row_length]
    
    pkg_file.close()
    
    if pin_col < 0:
        print("Could not determine pin column", file=sys.stderr)
        exit(1)
    
    if bank_col < 0:
        print("Could not determine bank column", file=sys.stderr)
        exit(1)
    
    if io_col < 0:
        print("Could not determine IO column", file=sys.stderr)
        exit(1)
    
    pins = [x[pin_col].lower() for x in pkg_contents]
    banks = [x[bank_col] for x in pkg_contents]
    ios = [x[io_col] for x in pkg_contents]
    
    print("Processing UCF file")
    
    try:
        input_file = open(input_name, 'r')
    except Exception as ex:
        print("Error opening \"%s\": %s" %(input_name, ex.strerror), file=sys.stderr)
        exit(1)
    
    try:
        output_file = open(output_name, 'w')
    except Exception as ex:
        print("Error opening \"%s\": %s" %(output_name, ex.strerror), file=sys.stderr)
        exit(1)
    
    for line in input_file:
        # deal with comments
        line_raw = line.split('#', 2)
        
        ucf_line = line_raw[0]
        
        ucf_line_l = ucf_line.lower()
        
        res = re.search('loc\s*=\s*\"(.+)\"', ucf_line_l)
        
        if res is not None:
            loc = res.group(1)
            
            try:
                i = pins.index(loc)
                
                bank = banks[i]
                io = ios[i]
                
                comment = " Bank = %s, %s" % (bank, io)
                
                if len(line_raw) == 1:
                    line_raw[0] += ' '
                    line_raw.append(comment)
                else:
                    c = line_raw[1]
                    
                    # strip old bank information
                    c = re.sub('\s*bank\s*=\s*(\d+|\?)\s*,\s*IO_(\w+|\?)', '', c, flags=re.IGNORECASE)
                    c = re.sub('\s*bank\s*=\s*(\d+|\?)\s*', '', c, flags=re.IGNORECASE)
                    c = re.sub('\s*IO_(\w+|\?)', '', c, flags=re.IGNORECASE)
                    
                    line_raw[1] = comment + c
                
            except ValueError:
                pass
            
        
        line_raw[0] = ucf_line
        
        line = '#'.join(line_raw)
        
        output_file.write(line)
    
    input_file.close()
    output_file.close()
    
    print("Wrote output file %s" % output_name)
    
    print("Done")
    

if __name__ == "__main__":
    main()

