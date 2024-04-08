#!/usr/bin/env python3

import csv
import pygal

class csvchart(object):
	def usage(self,argv0):
		return '''Usage: {} csv:METADATA1 csv:METADATA2 ... chart:file=chart.svg
where:
	METADATAx is a semicolon-separated list that identifies a CSV file, what fields to add to the visualization chart, and how to label them, e.g.
		csv:file=/path/to/data/file1.csv;x-field=date,time;y-fields=tempC csv:file=/path/to/data/file2.csv;x-field=date,time;y-fields=tempC,humidity;sides=left,right
'''.format(argv0)

	def parseargv(self, argv):
		self.sources = []
		chart = None
		labels = []
		for x in argv:
			if   x.startswith('csv:'):
				self._parsecsvmeta(x[4:])
			elif x.startswith('chart:'):
				self._parsechartmeta(x[6:])
			else:
				raise RuntimeError("unrecognized argument {}".format(x))
		if not hasattr(self,'chart'):
			self.chart=None

	def _parsemeta(self,m):
		if not m.endswith(';'):
			m = m + ';'
		tmp = {}
		for x in m.split(';'):
			if x == '': continue
			i = x.find('=')
			if i == -1:
				raise RuntimeError("error parsing metadata {}".format(x))
			l=x[:i]
			f=x[i+1:]
			if ',' in f:
				f = f.split(',')
			else:
				f = [f]
			if l in tmp:
				raise RuntimeError("second definition of {} in metadata".format(l))
			tmp[l]=f
		return tmp

	def _parsechartmeta(self,m):
		if hasattr(self,'chart'):
			raise RuntimeError("second definition of chart: {}".format(m))
		self.chart = self._parsemeta(m)
		self.chart['file']  = self.chart['file'][0]
		self.chart['title'] = self.chart['title'][0]
		if 'recwidth' in self.chart:
			self.chart['recwidth'] = int(self.chart['recwidth'][0])
		else:
			self.chart['recwidth'] = 10
		t = 'Line'
		if 'type' in self.chart:
			t = self.chart['type'][0]
		if   t == 'HorizontalBar':  self.chart['type'] = pygal.HorizontalBar
		elif t == 'StackedBar':  self.chart['type'] = pygal.StackedBar
		elif t == 'Bar':  self.chart['type'] = pygal.Bar
		elif t == 'HorizontalLine': self.chart['type'] = pygal.HorizontalLine
		elif t == 'StackedLine': self.chart['type'] = pygal.StackedLine
		elif t == 'Line': self.chart['type'] = pygal.Line
		else: self.chart['type'] = pygal.Line
		
		if 'interpolation' in self.chart:
			self.chart['interpolation'] = self.chart['interpolation'][0]
		else:
			self.chart['interpolation'] = None
		if 'secondary_range' in self.chart:
			self.chart['secondary_range'] = [float(v) for v in self.chart['secondary_range'] ]
		else:
			self.chart['secondary_range'] = None
		if 'value' in self.chart:
			self.chart['value'] = self.chart['value'][0]
		else:
			self.chart['value'] = 'last'
		if self.chart['value'] == 'average':
			self.chart['value'] = 'mean'
			# mean, total, min, max, count, first, last, confidence, maxconfidence

		# probably don't need this now that we do our own autoscaling
		if 'include_x_axis' in self.chart:
			self.chart['include_x_axis'] = self.chart['include_x_axis'][0]
			if self.chart['include_x_axis'].lower() == "true" or self.chart['include_x_axis'] == "1":
				self.chart['include_x_axis'] = True
			elif self.chart['include_x_axis'].lower() == "false" or self.chart['include_x_axis'] == "0":
				self.chart['include_x_axis'] = False
			else:
				print(f"Unrecognized value {self.chart['include_x_axis']} for include_x_axis, ignoring.", file=sys.stderr)
				self.chart['include_x_axis'] = False
		else:
			self.chart['include_x_axis'] = False


	def _parsecsvmeta(self,m):
		tmp = self._parsemeta(m)
		#tmp['x-field'] = tmp['x-field'][0]
		#tmp['file'] = tmp['file'][0]
		if not 'labels' in tmp:
			tmp['labels'] = tmp['y-fields']
		if not 'sides' in tmp:
			tmp['sides'] = ['left'] * len(tmp['labels'])
		
		self.sources.append(tmp)

	def summarize(self, preval, newval):
		preval['last'] = newval
		preval['count'] += 1
		if newval > preval['max']: 
			preval['max'] = newval
		if not hasattr(self, 'global_max') or newval > self.global_max:
			self.global_max = newval
		if newval < preval['min']: 
			preval['min'] = newval
		if not hasattr(self, 'global_min') or newval < self.global_min:
			self.global_min = newval
		preval['total'] += newval
		preval['mean'] = preval['total'] / preval['count']
		return preval

	def makedata(self):
		self.data = {}
		self.seenlabels = {} # global (this feels like a hack)
		for s in self.sources: # local
			seenlabels = {}
			fs=s['file']
			for f in fs:
				reader = csv.DictReader(open(f,'r'))
				try:
					for r in reader:
						#x = r[s['x-field']]
						x = '-'.join([r[k] for k in s['x-field']])
						if x not in self.data:
							self.data[x] = {}
						for f,l,c in zip(s['y-fields'],s['labels'],s['sides']):
							if not l in seenlabels:
								seenlabels[l]=c
							y = float(r[f])
							if l not in self.data[x]:
								self.data[x][l] = {'mean': 0, 'total': 0, 'min': y, 'max': y, 'count': 0, 'first': y, 'last': y}
							self.data[x][l] = self.summarize(self.data[x][l], y)
				except Exception as e:
					print(s,e,file=sys.stderr)
					raise e
			for l in seenlabels: # locally seen
				if l in self.seenlabels: # globally seen
					raise RuntimeError("Reuse of label {} from another dataset!".format(l))
				else:
					self.seenlabels[l] = seenlabels[l]
				
		# fill in sparse datasets
		for s in self.data:
			for l in self.seenlabels:
				if l not in self.data[s]:
					#self.data[s][l] = None
					self.data[s][l] = {'mean': None, 'total': None, 'min': None, 'max': None, 'count': 0, 'first': None, 'last': None}

					#d = r['date']
					#h = r['time'][:5]
					#s = d+"-"+h



if __name__ == '__main__':
	import sys
	from pygal.style import Style

	viz = csvchart()
	if len(sys.argv) <= 1:
		print(viz.usage(sys.argv[0]), file=sys.stderr)
		exit(1)
	viz.parseargv(sys.argv[1:])
	#print("sources")
	#for s in viz.sources: print("\t",s)
	if viz.chart is None:
		print("no chart provided", file=sys.stderr)
		print(viz.usage(sys.argv[0]),file=sys.stderr)
		exit(2)
	#print("chart")
	#print("\t",viz.chart)
	viz.makedata()
	#print("chart")
	#print("\t",viz.data)

	custom_style = Style(
		colors=('#0343df', '#e50000', '#929591', '#ffff14'),
		font_family='Roboto,Helvetica,Arial,sans-serif',
		background='transparent',
		label_font_size=14,
	)

	# width is computed based on number of records charted
	x_labels = list(viz.data.keys())
	width = len(x_labels) * viz.chart['recwidth']
	if width < 1200:
		width = 1200 # minimum width
	#c = pygal.Line(
	rang = (viz.global_min, viz.global_max)
	c = viz.chart['type'](
		include_x_axis=viz.chart['include_x_axis'],
		interpolate=viz.chart['interpolation'],
		title=viz.chart['title'],
		style=custom_style,
		#y_title=temp_unit,
		width=width,
		secondary_range=viz.chart['secondary_range'],
		range=rang,
		x_label_rotation=300,
	)
	c.x_labels = sorted(x_labels)

	# figure out what gets added to chart based on value= value in chart:... argument
	value = viz.chart['value']
	def guido(x,l):
		if value == "confidence":
			tmpvalue='mean'
			ci={'low':viz.data[x][l]['min'], 'high':viz.data[x][l]['max'] }
		elif value == "maxconfidence":
			tmpvalue='max'
			ci={'low':viz.data[x][l]['min'], 'high':viz.data[x][l]['max'] }
		elif value == "minconfidence":
			tmpvalue='min'
			ci={'low':viz.data[x][l]['min'], 'high':viz.data[x][l]['max'] }
		else:
			tmpvalue=value
			ci=None
		if viz.data[x][l][tmpvalue] is None: 
			return None # NOTE: need this to support interrupted lines
		o = {'value': round(viz.data[x][l][tmpvalue],2) }
		if ci is not None:
			o['ci'] = ci
		return o
	v = guido

	for l in viz.seenlabels:
		secondary = viz.seenlabels[l]=='right'
		c.add(l, [v(x,l) for x in c.x_labels], allow_interruptions=True, secondary=secondary)
	
	c.render_to_file(viz.chart['file'])
	exit(0)
