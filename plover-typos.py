#!/usr/bin/env python

# plover typos, suggest words to practice in plover
# Copyright (C) 2016  Jason Woofenden
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import re
import os
import sys
import argparse
import json

# SETTINGS:
DEFAULT_STROKES_LOG_PATH = os.getenv('XDG_DATA_HOME', os.getenv('HOME', '.') + '/.data') + '/plover/strokes.log'

ap = argparse.ArgumentParser(prog="plover_typos") # python 2.7 seems to not support: description="Find your common misstrokes", allow_abbrev=False)
ap.add_argument('-n', '--count', metavar='N', type=int, help="Max number of typos printed (default: 100)", default=100)
ap.add_argument('--score-bad', metavar='N.N', type=float, help="How many points are deducted for misstrokes? (Currect strokes score 1.) Default: 3", default=3)
ap.add_argument('--score-dampening', metavar='N.N', type=float, help="Lower values proirotize more recent strokes in score. 1.0 is uniform accross time. (default: 0.9)", default=0.9)
ap.add_argument('--min-stroke-count', metavar='N', type=int, help="Ignore strokes that have been typed fewer times than this (default: 15)", default=15)
ap.add_argument('--max-score', metavar='N.N', type=float, help="Only output strokes with a score worse than this (Default: 10)", default=10)
ap.add_argument('-j', '--json', dest="format", const="json", default="report", action='store_const', help="Set output format to JSON (default: txt report)")
ap.add_argument('filename', nargs='?', help="path to plover's strokes.log (default: " + DEFAULT_STROKES_LOG_PATH + ")", default=DEFAULT_STROKES_LOG_PATH)
args = ap.parse_args()

# new strokes.log format examples:
#
# typing a multi-stroke brief who's first stroke isn't in the dictionary:
#     2016-11-02 20:08:26,350 Stroke(PHREUT : ['P-', 'H-', 'R-', '-E', '-U', '-T'])
#     2016-11-02 20:08:26,355 Translation(('PHREUT',) : None)
#     2016-11-02 20:08:39,777 Stroke(KAL : ['K-', 'A-', '-L'])
#     2016-11-02 20:08:39,778 *Translation(('PHREUT',) : None)
#     2016-11-02 20:08:39,778 Translation(('PHREUT', 'KAL') : "political")
# typing a multi-stroke brief who's first stroke is in the dictionary:
#     2016-11-02 20:14:02,767 Stroke(EBGS : ['-E', '-B', '-G', '-S'])
#     2016-11-02 20:14:02,770 Translation(('EBGS',) : "ex")
#     2016-11-02 20:14:06,721 Stroke(PAPBGS : ['P-', 'A-', '-P', '-B', '-G', '-S'])
#     2016-11-02 20:14:06,721 *Translation(('EBGS',) : "ex")
#     2016-11-02 20:14:06,722 Translation(('EBGS', 'PAPBGS') : "expansion")
# typing two words, then deleting both:
#     2016-11-02 20:15:02,027 Stroke(HAOEU : ['H-', 'A-', 'O-', '-E', '-U'])
#     2016-11-02 20:15:02,030 Translation(('HAOEU',) : "high")
#     2016-11-02 20:15:03,070 Stroke(THR : ['T-', 'H-', 'R-'])
#     2016-11-02 20:15:03,071 Translation(('THR',) : "there")
#     2016-11-02 20:15:03,901 *Stroke(* : ['*'])
#     2016-11-02 20:15:03,903 *Translation(('THR',) : "there")
#     2016-11-02 20:15:04,068 *Stroke(* : ['*'])
#     2016-11-02 20:15:04,071 *Translation(('HAOEU',) : "high")
# typing then deleting a two-stroke word
#     2016-11-02 20:16:23,022 Stroke(EBGS : ['-E', '-B', '-G', '-S'])
#     2016-11-02 20:16:23,023 Translation(('EBGS',) : "ex")
#     2016-11-02 20:16:26,365 Stroke(TAPBGS : ['T-', 'A-', '-P', '-B', '-G', '-S'])
#     2016-11-02 20:16:26,366 *Translation(('EBGS',) : "ex")
#     2016-11-02 20:16:26,367 Translation(('EBGS', 'TAPBGS') : "expansion")
#     2016-11-02 20:16:27,353 *Stroke(* : ['*'])
#     2016-11-02 20:16:27,354 *Translation(('EBGS', 'TAPBGS') : "expansion")
#     2016-11-02 20:16:27,354 Translation(('EBGS',) : "ex")
#     2016-11-02 20:16:27,535 *Stroke(* : ['*'])
#     2016-11-02 20:16:27,537 *Translation(('EBGS',) : "ex")
# typing a word, then sepress space then delete
#     2016-11-02 23:49:00,222 Stroke(SEUPL : ['S-', '-E', '-U', '-P', '-L'])
#     2016-11-02 23:49:00,223 Translation(('SEUPL',) : "similar")
#     2016-11-02 23:49:02,183 Stroke(TK-LS : ['T-', 'K-', '-L', '-S'])
#     2016-11-02 23:49:02,184 Translation(('TK-LS',) : "{^^}")
#     2016-11-02 23:49:04,160 *Stroke(* : ['*'])
#     2016-11-02 23:49:04,161 *Translation(('SEUPL',) : "similar")
#     2016-11-02 23:49:04,163 *Translation(('TK-LS',) : "{^^}")

# keep stats here
scores = {}

tries = [0] # the first item affects the score of the _next_ word typed

# constants to track state of parser
OLD_FORMAT = 0
NORMAL = 1
DELETING = 2 # and this one is used for fun as a dummy value in the blacklist

# These throw off the statistics, because they don't take a separate delete
# stroke to delete. Ignore them
event_blacklist = {
	"Stroke(TK-LS : ['T-', 'K-', '-L', '-S'])": DELETING,
	"Translation(('TK-LS',) : \"{^^}\")": DELETING,
	"*Translation(('TK-LS',) : \"{^^}\")": DELETING,
	"Translation(('TKUPT',) : \"{PLOVER:ADD_TRANSLATION}\")": DELETING,
	"*Translation(('TKUPT',) : \"{PLOVER:ADD_TRANSLATION}\")": DELETING,
	"Stroke(KPA : ['K-', 'P-', 'A-'])": DELETING,
	"Translation(('KPA',) : \"{}{-|}\")": DELETING,
	"Stroke(KPA* : ['K-', 'P-', 'A-', '*'])": DELETING,
	"Translation(('KPA*',) : \"{^}{-|}\")": DELETING,
	"*Stroke(* : ['*'])": DELETING,
	"*Translation(('-GS',) : \"{^s}\")": DELETING,
	"*Translation(('KPA',) : \"{}{-|}\")": DELETING,
	"*Translation(('KPA*',) : \"{^}{-|}\")": DELETING,
}

state = OLD_FORMAT
def score_init(word, date):
	if word in scores:
		return
	scores[word] = {"count": 0, "score": 10, "date": date}
	
def points(word, date):
	score_init(word, date)
	scores[word]['count'] += 1
	if tries[0] == 0: # first try
		scores[word]['score'] *= args.score_dampening
		scores[word]['score'] += 1
	else:
		for i in range(0, tries[0]):
			scores[word]['score'] *= args.score_dampening
			scores[word]['score'] -= args.score_bad
	scores[word]['date'] = date
def undo_points(word, date):
	score_init(word, date)
	scores[word]['count'] -= 1
	if tries[0] == 0: # first try
		scores[word]['score'] -= 1
		scores[word]['score'] /= args.score_dampening
	else:
		for i in range(0, tries[0]):
			scores[word]['score'] += args.score_bad
			scores[word]['score'] /= args.score_dampening

new_log_format = re.compile('^Stroke\\(.*:')

translation_text = re.compile('"(.*)"')
def extract_translation(event):
	matches = translation_text.search(event)
	if matches is None:
		return ''
	else:
		return matches.group(1)

with open(args.filename, 'rt') as log_file:
	for line in log_file:
		date, time, event = line.strip().split(' ', 2)
		if state == OLD_FORMAT:
			if new_log_format.match(event):
				state = NORMAL
				# fall through
			else:
				continue
		if event == "*Stroke(* : ['*'])":
			state = DELETING
			# delay acton 'til we know what the translation is
			continue
		if event in event_blacklist:
			continue
		if event.startswith('*Translation'):
			word = extract_translation(event)
			# pop then score
			if len(tries) > 1:
				tries.pop(0)
			else:
				# ran out of history, just reset
				tries[0] = 0
			if word != '':
				undo_points(word, date)
			if state == DELETING:
				state = NORMAL
				tries[0] += 1
		elif event.startswith('Translation'):
			# a normal stroke
			word = extract_translation(event)
			# score then push
			if word != '':
				points(word, date)
			tries.insert(0, 0) # prepend a zero
			if len(tries) > 50:
				tries.pop()

baddies = []
for word in scores:
	if scores[word]['count'] >= args.min_stroke_count and scores[word]['score'] < args.max_score:
		baddies.append([scores[word]['score'], word])
def compare_first(a, b):
	if a[0] > b[0]:
		return 1
	return 0
baddies.sort(key=lambda baddy: baddy[0], reverse=True)
if len(baddies) > args.count:
	baddies = baddies[(len(baddies) - args.count):]
if args.format == 'json':
	print(json.dumps(map((lambda a: a[1]), baddies)))
else:
	if len(baddies) > 0:
		print("Troublesome words:  (worst offenders shown last)\n")
		for word in baddies:
			print("   %s: %f" % (word[1], word[0]))
	else:
		print("No matches found")
