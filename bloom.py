#!/usr/bin/env python
#
# Copyright 2018 Carter Yagemann
#
# This file is part of Barnum.
#
# Barnum is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Barnum is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Barnum.  If not, see <https://www.gnu.org/licenses/>.

import sys
import os
import reader
import logger
import filters
from optparse import OptionParser
from pybloom import ScalableBloomFilter

module_name = 'Bloom'

def load_set(filepath):
    res = {'b_train': []}
    set_key = ''
    with open(filepath, 'r') as ifile:
        for line in ifile:
            line = line.rstrip()
            if len(line) < 1:
                continue
            if line[0] == '[':
                set_key = line[1:-1]
            else:
                if set_key in res.keys():
                    res[set_key].append(line)
    return res

def process_trace(dir, seq_len):
    trace_filepath = os.path.join(dir, 'trace_parsed.gz')
    if not os.path.isfile(trace_filepath):
        sys.stdout.write('Could not find ' + str(trace_filepath))
        return

    seq = list()
    seen = ScalableBloomFilter()  # Only consider a sequence once per trace
    count = 0
    total = 0

    for tuple in reader.read_preprocessed(trace_filepath):
        if tuple is None:
            break  # end of trace
        curr_size = len(seq)
        if curr_size < (seq_len - 1):
            seq.append(tuple[0])
        elif curr_size == (seq_len - 1):
            seq.append(tuple[0])
            # We only want to send sequences that end in an indirect control flow transfer
            if True in [func(tuple) for func in filters.enabled_filters]:
                if not bloom.add(str(seq)):
                    count += 1
                if not seen.add(str(seq)):
                    total += 1
        else:
            seq.pop(0)
            seq.append(tuple[0])
            # We only want to send sequences that end in an indirect control flow transfer
            if True in [func(tuple) for func in filters.enabled_filters]:
                if not bloom.add(str(seq)):
                    count += 1
                if not seen.add(str(seq)):
                    total += 1

    sys.stdout.write(str(count) + "," + str(total) + "," + str(float(count) / float(total)) + "\n")
    sys.stdout.flush()

def process_set(dirs, key, seq_len):
    sys.stdout.write('-- ' + str(key) + " --\n")
    count = 0
    for dir in dirs:
        sys.stderr.write(str(count) + "\r")
        sys.stderr.flush()
        process_trace(dir, seq_len)
        count += 1

def main():
    global bloom

    # Parse input arguments
    parser = OptionParser(usage='Usage: %prog [options] input_set')
    parser.add_option('-r', '--parse-ret', action='store_true', dest='parse_ret',
                      help='Consider returns')
    parser.add_option('-c', '--parse-icall', action='store_true', dest='parse_icall',
                      help='Consider indirect calls')
    parser.add_option('-j', '--parse-ijmp', action='store_true', dest='parse_ijmp',
                      help='Consider indirect jumps')
    parser.add_option('-s', '--sequence-length', action='store', dest='seq_len', type='int', default=32,
                      help='Sequence lengths to use (default: 32)')

    options, args = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        sys.stdout.write("\n  Note: Only preprocessed traces are supported\n")
        sys.exit(1)

    set_filepath = args[0]

    # Input validation
    if not os.path.isfile(set_filepath):
        sys.stderr.write('Error: ' + str(set_filepath) + " either does not exist or is not a file\n")
        sys.exit(1)

    if options.parse_ret:
        filters.add_filter('ret')

    if options.parse_icall:
        filters.add_filter('icall')

    if options.parse_ijmp:
        filters.add_filter('ijmp')

    if filters.get_num_enabled() == 0:
        sys.stderr.write("Error: Must specify at least one thing to learn (-r, -c, -j)\n")
        sys.exit(1)

    # Initialization
    set = load_set(set_filepath)
    logger.log_start(20)
    bloom = ScalableBloomFilter()

    # Work
    try:
        logger.log_info(module_name, 'Parsing training set')
        process_set(set['b_train'], 'b_train', options.seq_len)
        logger.log_info(module_name, 'Parsing testing set')
        process_set(set['b_test'], 'b_test', options.seq_len)
    except KeyboardInterrupt:
        sys.stderr.write("Keyboard Interrupt\n")
        logger.log_stop()
        sys.exit(2)

    # Cleanup
    logger.log_stop()

if __name__ == '__main__':
    main()
