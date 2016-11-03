About
=====

plover-typos: generate a report of frequent/recent typos you made in plover

USAGE
-----

	usage: plover-typos [-h] [-n N] [--score-bad N.N] [--score-dampening N.N]
                    	[--min-stroke-count N] [--max-score N.N] [-j]
                    	[filename]

	positional arguments:
  	  filename              path to plover's strokes.log

	optional arguments:
  	  -h, --help            show this help message and exit
  	  -n N, --count N       Max number of typos printed (default: 100)
  	  --score-bad N.N       How many points are deducted for misstrokes? (Currect
                        	strokes score 1.) Default: 3
  	  --score-dampening N.N
                        	Lower values proirotize more recent strokes in score.
                        	1.0 is uniform accross time. (default: 0.9)
  	  --min-stroke-count N  Ignore strokes that have been typed fewer times than
                        	this (default: 15)
  	  --max-score N.N       Only output strokes with a score worse than this
                        	(Default: 10)
  	  -j, --json            Set output format to JSON (default: txt report)
