#!/usr/bin/python2.3
DEBUG = 1

import sys, types, string

from pysqlite2 import dbapi2 as sqlite

options		= {
				'waiting':	{'New':'waiting.new()', 'Replace':'waiting.replace()', 'Delete':'waiting.delete()', 'Complete':'waiting.complete()', 'Quit':'setContext("main")'},
				'main':		{'New':'action.new()', 'Replace':'action.replace()', 'Delete':'action.delete()', 'Complete':'action.complete()', 'Waiting':'setContext("waiting")', 'List':'action.list()', 'Quit':'exit()'},
			  }

context		= 'main'
query		= ''

database	= sqlite.connect("gtd.sqli")
cursor		= database.cursor()

class userInterface:

	def list(self):
		global query
		
		# take the input and figure out if any projects and contexts are specified
		# remove the "list" action that will be first on user's input
		input		= query.split(' ')[1:]
		# now parse it
		input		= parseTags(" ".join(input))
		
		if input['action'].split(' ')[0] == 'projects':
			# group by projects
			projecting	= Projects()
			projecting.list()
			return

		if input['action'].split(' ').pop(0) == 'somedays':
			# list someday/maybes
			table	= 'someday'
		else:
			table	= 'action'
			
		if input['action'] == 'completed':
			# only show completed items
			completeCondition	= table + 's.datecomplete IS NOT NULL'
		elif input['action'] == 'all':
			# show all items
			completeCondition	= '(' + table + 's.datecomplete IS NOT NULL OR ' + table + 's.datecomplete IS NULL)'
		else:
			# show only incomplete items
			completeCondition	= table + 's.datecomplete IS NULL'
			
		# limit the listing by context
		if input['contexts']:
			contextJoin			= ' LEFT JOIN context' + table + 'map map ON (map.' + table + 'id = ' + table + 's.id) \
									LEFT JOIN contexts ON (map.contextid = contexts.id)'
			contextCondition	= ' AND contexts.description IN (' + ', '.join(["'" + str(x) + "'" for x in input['contexts']]) + ')'
		else:
			contextJoin			= ''
			contextCondition	= ''
		
		# limit the listing by project
		if input['projects'] and table in ('action', 'agenda', 'waitingfor'):
			projectJoin			= ' LEFT JOIN project' + table + 'map map ON (map.' + table + 'id = ' + table + 's.id) \
									LEFT JOIN projects ON (map.projectid = ' + table + 's.id)'
			projectCondition	= ' AND projects.description IN (' + ', '.join(["'" + str(x) + "'" for x in input['projects']]) + ')'
		else:
			projectJoin			= ''
			projectCondition	= ''

		cursor.execute('SELECT ' + table + 's.id, ' + table + 's.description, DATE(' + table + 's.dateadd) AS dateadded, DATE(' + table + 's.datecomplete) AS datecomplete FROM ' + table + 's'  + contextJoin + projectJoin + ' WHERE ' + completeCondition + contextCondition + projectCondition)

		print ""
		print string.rjust('id', 4) + "  " + string.ljust('description', 50) + string.ljust('added', 10) + '  ' + string.ljust('completed', 10)
		print "="*78

		#contextList	= {}
		#projectList	= {}
		
		for row in cursor.fetchall():
			print string.rjust(str(row[0]), 4) + "  " + string.ljust(str(row[1]), 50) + string.ljust(str(row[2]), 10) + '  ' + string.ljust(str(row[3]), 10)
			
		print ""

class ContextProjects:
	"""This class is the super for both Contexts and Projects."""

	map	= {'action': {'context': 'contextactionmap', 'project': 'projectactionmap'} }
	
	def disassociate(self, id, h, i):
		"""Will dissasociate a project/context (i) from an action. (h) """
		
		# first, check to make sure that our arguments are valid
		if not self.map.has_key(h):
			raise Exception("h is not a valid type.")
			return
			
		if not self.map[h].has_key(i):
			raise Exception("Can't disassociate from the object i ", i)
			return
			
		#if i == 'table':
		#	raise Exception("Very funny, but table is a pseudo object in self.map, not a valid type.")
		#	return
			
		# first, get the ids of the object we're disassociating with for use later
		cursor.execute('SELECT ' + i + 'id FROM ' + map[h][i] + ' WHERE ' + h + 'id = ?', (id, ))
		
		# id's of potential contexts/projects to delete
		cleanupIds	= []
		
		for row in cursor.fetchall():
			cleanupIds.append(int(row[0]))

	def removeMap(self, id, type, table):
		"""removeMap will disassociate all contexts or projects from an action or
		other object."""

		global database, cursor
		
		cursor.execute('DELETE FROM ' + table + ' WHERE ' + type + 'id = ?', (id, ))
		# now clean up the table of all unassociated contexts & projects
		# todo: make this more elegant
		cursor.execute('DELETE FROM projects WHERE id IN (SELECT id FROM projects LEFT JOIN projectactionmap map ON (map.projectid = projects.id) WHERE map.projectid IS NULL)')
		cursor.execute('DELETE FROM contexts WHERE id IN (SELECT id FROM contexts LEFT JOIN contextactionmap map ON (map.contextid = contexts.id) LEFT JOIN contextsomedaymap map2 ON (map2.contextid = contexts.id) WHERE map.contextid IS NULL AND map2.contextid IS NULL)')
		database.commit()

class Contexts(ContextProjects):

	# associate the type argument we'll get
	# and figure out what table to query
	mapping	= {'action':'contextactionmap'}	

	def insertContext(self, contextName, id, type="action"):
		"""contexts.insertContext will insert the mapping necessary
		to map a context between the context _context and _type object
		with _id."""

		global database, cursor
		
		if not Contexts.mapping.has_key(type):
			raise Exception('The specified type argument is invalid.')
			return false
			
		cursor.execute('SELECT id FROM contexts WHERE description LIKE ?', (contextName, ))
		contextId	= cursor.fetchone()
		
		if contextId == None: 
			#context doesn't exist, create it
			cursor.execute('INSERT INTO contexts (description) VALUES (?)', (contextName, ))
			database.commit()
			contextId	= cursor.lastrowid
		else:
			contextId	= contextId[0]

		cursor.execute('INSERT INTO ' + Contexts.mapping[type] + ' (contextid, ' + type + 'id) VALUES (?, ?)', (contextId, id))
		database.commit()
		
	def removeMap(self, id, type):
		"""Wrapper for the parent function removeMap."""
		
		if not Contexts.mapping.has_key(type):
			raise Exception('The specified type argument is invalid.')
			return false
		
		parent	= ContextProjects()
		parent.removeMap(id, type, Contexts.mapping[type])
		del parent
		

		
class Projects(ContextProjects):
	"""Implements actions for creating, selecting, deleting,
	and dealing with p: projects."""

	# associate the type argument we'll get
	# and figure out what table to work on
	validTypes	= {'action':'projectactionmap'}
	
	def insertProject(self, projectName, id, type="action"):
		"""Associates an action/agenda with a project, will also handle the
		creation of new projects if the project isn't available already."""

		global database, cursor
		
		if not Projects.validTypes.has_key(type):
			raise Exception('Supplied argument type is not an object this function works with.')
			return false
			
		cursor.execute('SELECT id FROM projects WHERE description LIKE ?', (projectName, ))
		projectId	= cursor.fetchone()
		
		if projectId == None: 
			# project doesn't exist, create it
			cursor.execute('INSERT INTO projects (description) VALUES (?)', (projectName, ) )
			database.commit()
			projectId	= cursor.lastrowid
		else:
			projectId	= projectId[0]

		cursor.execute('INSERT INTO ' + Projects.validTypes[type] + ' (projectid, ' + type + 'id) VALUES (?, ?)', (projectId, id))
		database.commit()
		
	def removeMap(self, id, type):
		"""Wrapper for the parent function removeMap."""
		
		if not Projects.validTypes.has_key(type):
			raise Exception('The specified type argument is invalid.')
			return false
		
		parent	= ContextProjects()
		parent.removeMap(id, type, Projects.validTypes[type])
		del parent
		
	def list(self):
		"""Gives you a view of all defined projects. Projects.List() will also
		apply any project/context filtering it finds in user input."""
		
		global query
		
		# take the input and figure out if any projects and contexts are specified

		# remove the "list" action that will be first on user's input
		input		= query.split(' ')[2:]

		# now parse user input
		input		= parseTags(" ".join(input))
		
		# limit the listing by context
		if input['contexts']:
			contextJoin			= ' INNER JOIN contextactionmap ON (contextactionmap.actionid = actions.id) \
									INNER JOIN contexts ON (contextactionmap.contextid = contexts.id)'
			contextCondition	= ' AND contexts.description IN (' + ', '.join(["'" + str(x) + "'" for x in input['contexts']]) + ')'
		else:
			contextJoin			= ''
			contextCondition	= ''
		
		# limit the listing by project
		if input['projects']:
			projectCondition	= ' AND projects.description IN (' + ', '.join(["'" + str(x) + "'" for x in input['projects']]) + ')'
		else:
			projectCondition	= ''
			
		if input['action'] == 'completed':
			# only show completed tasks
			completeCondition	= 'actions.datecomplete IS NOT NULL'
		elif input['action'] == 'all':
			# show all actions
			completeCondition	= '(actions.datecomplete IS NOT NULL OR actions.datecomplete IS NULL)'
		else:
			# show only incomplete actions (default)
			completeCondition	= 'actions.datecomplete IS NULL'

		projects	= {}
		actions		= {}
			
		cursor.execute('SELECT \
						projects.id,  \
						projects.description, \
						DATE(projects.dateadded), \
						actions.id, \
						actions.description, \
						DATE(actions.dateadd), \
						DATE(actions.datecomplete) \
						FROM projects \
						LEFT JOIN projectactionmap map ON (projects.id = map.projectid) \
						LEFT JOIN actions ON (actions.id = map.actionid) \
						' + contextJoin + '\
						WHERE ' + completeCondition + contextCondition + projectCondition)
		
		for row in cursor.fetchall():

			# create a dictionary for every project, to contain each action's info				
			if not actions.has_key(row[0]):
				actions[row[0]]	= {}
					
			# now insert this action's info into a dictionary for this project
			actions[row[0]][row[3]]		= { "description": row[4], "dateadd": row[5], "datecomplete": row[6]}

			# insert info about every project in a special dictionary
			if not projects.has_key(row[0]):				
				projects[row[0]]	= { "description": row[1], "dateadded": row[2]}
			
		# print title info
		print string.rjust('id', 4) + "  " + string.ljust('project name', 50) + string.ljust('added', 10) + "  " + string.ljust('completed', 10)
		print '-' * 78
			
		# loop through the projects
		for h, i in projects.iteritems():
			print string.rjust(str(h), 4) + "  " + string.ljust(str(i["description"]), 50) + string.ljust(str(i["dateadded"]), 10)
			print '=' * 78
				
			for j, k in actions[h].iteritems():
				print string.rjust(str(j), 4) + "  " + string.ljust(str(k["description"]), 50) + string.ljust(str(k["dateadd"]), 10) + "  " + string.ljust(str(k["datecomplete"]), 10)
			
class WaitingFor:
	pass
	
class NextAction:
	def new(self):
		global query, database, cursor
		
		input	= query.split(' ')[1:]
		input	= " ".join(input)
		action	= parseTags(input)
		
		if len(action['action'].strip()) == 0:
			print "No action specified."
		else:
			cursor.execute("INSERT INTO actions (description) VALUES (?)", (action['action'], ) )
			database.commit()
			
			actionId	= cursor.lastrowid
			
			contexting	= Contexts()
			projecting	= Projects()

			# for every context/project specified, add it in
			for elem in action['contexts']:
				contexting.insertContext(elem, actionId, 'action')
				
			for elem in action['projects']:
				projecting.insertProject(elem, actionId, 'action')

		print 'task "' + action['action'] + '"  added to the Next Action list.'
		
	def replace(self):
		"""NextAction.replace() will read the command line for an id of a task
		to replace, and the text to replace it with. The id of the task must be
		the first argument the user gives, or an error will be displayed."""
		
		global query, database, cursor
		
		# remove the "replace" action that will be first on user's input
		input		= query.split(' ')[1:]
		# grab the id of the action we are to replace, which should be
		# the first argument
		replaceId	= input.pop(0)
		# now parse the rest of the input for actions, projects, contexts
		action		= parseTags(" ".join(input))

		self.changeState(replaceId, 'replace', action)
			
	def delete(self):
		"""NextAction.delete() will read the command line for an id of a task
		to delete, and will delete the task and all associated maps."""
		
		global query, database, cursor
		
		# remove the "delete" action that will be first on user's input
		input		= query.split(' ')[1:]
		# grab the id of the action we are to replace, which should be
		# the first argument
		deleteId	= input.pop(0)

		self.changeState(deleteId, 'delete')
			
	def complete(self):
		"""NextAction.complete() will read the command line for an id of a task
		to complete, and will set the task's datecomplete column to today's date."""
		
		global query, database, cursor
		
		# remove the "delete" action that will be first on user's input
		input		= query.split(' ')[1:]
		# grab the id of the action we are to complete, which should be
		# the first argument
		completeId	= input.pop(0)

		self.changeState(completeId, 'complete')		
			
	def changeState(self, id, action, actionObj=""):
		"""NextAction.changeState() will handle the meat of completing, deleting
		and replacing an action. To be called by other functions."""
		
		global database, cursor
		
		validActions	= ('complete', 'delete', 'replace')
		
		if action not in validActions:
			raise Exception('The argument action=' + action +' is not valid.')
		
		# figure out if id is a valid action
		cursor.execute("SELECT id, description FROM actions WHERE id LIKE ?", (id, ))
		oldAction	= cursor.fetchone()
		
		if oldAction == None:
			print "The id of the action you specified is invalid."
			return
		elif int(oldAction[0]) != int(id):
			raise Exception("The returned id from the database was not the same as the specified id.")
			return
		else:
			if action in ('delete', 'replace'):
				# right now, go ahead and disassociate the action from all projects and actions.
				contexting	= Contexts()
				projecting	= Projects()
			
				contexting.removeMap(id, "action")
				projecting.removeMap(id, "action")
			
			# the real meat, delete, complete or replace depending on what's specified
			if action == 'delete':
				# delete it
				cursor.execute("DELETE FROM actions WHERE id=?", (id, ))
			elif action == 'replace':
				# replace it
				cursor.execute("UPDATE actions SET description=? WHERE id=?", (actionObj['action'], id))
			elif action == 'complete':
				cursor.execute("UPDATE actions SET datecomplete=datetime('now') WHERE id=? AND datecomplete IS NULL", (id, ))

			database.commit()

			if action == 'replace':
				# if we replaced it, we can now go back and reassociate projects/actions
				for elem in actionObj['contexts']:
					contexting.insertContext(elem, id, 'action')
				
				for elem in actionObj['projects']:
					projecting.insertProject(elem, id, 'action')
					
				del projecting
				del contexting
				
			print 'Action "' + oldAction[1] + '" ' + action + 'd.'
			
	def list(self):
		ui	= userInterface()
		ui.list()
		del ui

action	= NextAction()
waiting	= WaitingFor()

def parseTags (toParse):
	"""Returns three lists: the contexts, the projects, a string of the action description."""

	toParse		= toParse.split(' ')
	contexts	= [elem for elem in toParse if elem.find('@') == 0]
	projects	= [elem for elem in toParse if elem.find('p:') == 0]
	actionDesc	= [elem for elem in toParse if elem.find('@') != 0 and elem.find('p:') != 0]
	
	return { "contexts": contexts, "projects": projects, "action": " ".join(actionDesc)}

def setContext (newContext):
	global context
	
	if DEBUG:
		print "DEBUG: context switched to ", newContext
	context	= newContext
	handleMenu()

def handleMenu():
	global context, query
	
	try:
		#if context == 'main':
		#	action.list()

		#for x in options[context]:
		#	print '\t-' + x

		if not sys.argv[1:]:
			query		= raw_input('Select a ' + context + ' option: ')
			exitSoon	= 0
		else:
			query 		= str("".join(sys.argv[1:]))
			exitSoon	= 1

		if not options[context].has_key(query.strip().lower().capitalize().split(' ')[0]):
			print "Choose another option"
			handleMenu()
		else:
			#print "Execute: ", options[context][query.strip().lower().capitalize()]
			exec(options[context][query.strip().lower().capitalize().split(' ')[0]])
			
			if not exitSoon:
				handleMenu()

		#if query.strip().lower().capitalize().split(' ')[0] == "Quit":
		#	print 'quitting'
		#	sys.exit(0)
		#	print 'Not recognized. Try again.'

	except (EOFError, KeyboardInterrupt):
		exit()

def exit():
	sys.exit(0)	

handleMenu()