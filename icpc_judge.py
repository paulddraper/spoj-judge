import datetime
import itertools
import os
import sqlite3
import sys
import time

def create_db():
	conn = sqlite3.connect(':memory:', detect_types=sqlite3.PARSE_DECLTYPES)
	conn.row_factory = sqlite3.Row
	conn.execute('''create table language (
		id integer
		name text
	)''')
	conn.execute('''create table contest (
		start_gz integer
		, end_gz integer
		, sol_limit integer
		, code text
		, name text
		, now timestamp
	)''')
	conn.execute('''create table problem (
		id integer
		, time_limit integer
		, code text
		, name text
		, problem_type_id integer
		, pset text
		, start_gz integer
		, end_gz integer
		, info text
		, problem_setter_id integer
		, source text
	)''')
	conn.execute('''create table problem_type (
		id integer
		, name text
	)''')
	conn.execute('''create table user (
		id integer
		, username text
		, name text
		, school text
		, email text
		, info1 text
		, info2 text
		, start timestamp
		, end timestamp
	)''')
	conn.execute('''create table submission (
		user_id integer
		, problem_id integer
		, submit_gz integer
		, status_id integer
		, language_id integer
		, score real
		, time real
		, date datetime
		, submission_id
	)''')
	conn.execute('''create table status (
		id integer
		, name text
	)''')
	return conn

def load_db(conn, input):
	next = lambda: input.readline().replace('\n','')

	insert_values_sql = lambda table, n_fields: (
			'insert into {0} values ({1})'
			.format(table, ','.join(['?']*n_fields))
		)

	#contest
	n_lines = int(next())
	record = [next() for _ in range(n_lines)][:6]
	conn.execute(insert_values_sql('contest', 6), record)

	#problem
	n_records = int(next())
	n_lines = int(next())
	records = [[next() for j in range(n_lines)][:11] for i in range(n_records)]
	conn.executemany(insert_values_sql('problem', 11), records)

	#problem_type
	records = [(0, 'CLASSICAL'), (1, 'CHALLENGE')]
	conn.executemany(insert_values_sql('problem_type', 2), records)

	#user
	n_records = int(next())
	n_lines = int(next())
	records = [[next() for j in range(n_lines)][:9] for i in range(n_records)]
	conn.executemany(insert_values_sql('user', 9), records)

	#submission
	next() #?
	n_lines = int(next())
	next() #?
	n_records = int(next())
	records = [[next() for j in range(n_lines)][:9] for i in range(n_records)]
	conn.executemany(insert_values_sql('submission', 9), records)

	#status
	records = [(15, 'CORRECT')]
	conn.executemany(insert_values_sql('status', 2), records)

def calc_stats(conn):
	#user_problem
	conn.execute('''create table user_problem as
		select
			u.id user_id
			, p.id problem_id
			, min(case when st.name = 'CORRECT' then s.submit_gz - c.start_gz end) seconds
		from contest c, user u, problem p
			left join submission s on u.id = s.user_id and s.problem_id = p.id
			left join status st on s.status_id = st.id
		group by u.id, p.id
	''')
	conn.execute('''alter table user_problem add column incorrect int''')
	conn.execute('''update user_problem
		set incorrect = (
			select count(*)
			from contest c, submission s
				left join status st on s.status_id = st.id
			where (st.name is null or st.name <> 'CORRECT')
				and s.date - c.start_gz < user_problem.seconds 
				and user_problem.user_id = s.user_id and user_problem.problem_id = s.problem_id
		)
	''')
	
	#user
	conn.execute('''alter table user add column score integer''')
	conn.execute('''alter table user add column time_penalty integer''')
	conn.execute('''alter table user add column rank integer''')
	conn.execute('''update user
		set score = (
			select count(case when seconds is not null then 1 end)
			from user_problem up where up.user_id = user.id
		)
		, time_penalty = (
			select ifnull(sum(case when seconds is not null then seconds end), 0)
				+ 20 * 60 * ifnull(sum(case when seconds is not null then incorrect end), 0)
			from user_problem up, contest c where up.user_id = user.id
		)
	''')
	conn.execute('''update user
		set rank = 1 + (select count(*) from user u where u.score > user.score
			or (u.score = user.score and u.time_penalty < user.time_penalty))
	''')

def time_grid(conn):
	date = conn.execute('''select now from contest''').fetchone()['now']
	s = (
		'Ranking last updated '
		'<script>document.write(new Date({utc}*1000).toLocaleString());</script>'
	).format(utc=time.mktime(date.timetuple()))
	return [[s]]

def ranking_grid(conn):
	grid = []

	contest = conn.execute('''select code from contest''').fetchone()

	row = []
	row.append('Rank')
	row.append('Name')
	row += (
		'<a href="/{c[code]}/problems/{p[code]}/">'
			'<font title="{p[name]}">{p[code]}</font>'
		'</a>'.format(c=contest, p=problem)
		for problem
		in conn.execute('''select code, name from problem order by id''')
	)
	row.append('Score')
	row.append('Time')
	grid.append(row)

	for user in conn.execute('''
			select id, username, name, score, time_penalty, rank
			from user
			order by rank, username
		'''):

		row = []
		row.append('{u[rank]}'.format(u=user))
		row.append(
			'<a href="/{c[code]}/users/{u[username]}/">{u[name]}</a>'
			.format(c=contest, u=user)
		)
		for user_problem in conn.execute('''
				select p.code, pt.name type_name, up.seconds, up.incorrect
				from problem p
					left join user_problem up on p.id = up.problem_id and up.user_id = ?
					left join problem_type pt on p.problem_type_id = pt.id
				order by p.id
			''', (user['id'],)):

			display = ''
			if user_problem['seconds']:
				display += sec_to_str(user_problem['seconds'])
			if user_problem['incorrect']:
				display += '<br/>(+{})'.format(20*60*user_problem['incorrect'])
			row.append(
				'<a href="/{c[code]}/status/{up[code]},{u[username]}/">{display}</a>'
				.format(c=contest, u=user, up=user_problem, display=display)
				if display else ''
			)
		row.append('{u[score]}'.format(u=user))
		row.append(sec_to_str(user['time_penalty']))
		grid.append(row)

	return grid

def sec_to_str(seconds):
	return str(datetime.timedelta(seconds=seconds))

def grid_to_string(grid):
	return '\n'.join(itertools.chain(
		(str(len(grid[0])),),
		grid[0],
		(str(len(grid[1:])),),
		(element for row in grid[1:] for element in row),
		(str(),)
	))

if __name__ == '__main__':
	conn = create_db()

	in_file = os.fdopen(0, 'r') if len(sys.argv) == 1 else open(sys.argv[1], 'r')
	load_db(conn, in_file)
	in_file.close()

	calc_stats(conn)

	out_file = os.fdopen(6, 'w') if len(sys.argv) == 1 else sys.stdout
	out_file.write('2\n')
	out_file.write(grid_to_string(time_grid(conn)))
	out_file.write(grid_to_string(ranking_grid(conn)))
	out_file.close()

	conn.close()
