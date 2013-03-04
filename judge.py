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
	conn.execute('''create table user_problem as
		select
			u.id user_id
			, p.id problem_id
			, max(case st.name when 'CORRECT' then s.score end) best 
			, min(case st.name when 'CORRECT' then s.time end) fastest
			, min(case st.name when 'CORRECT' then s.submit_gz end) soonest
		from user u
			left join submission s on u.id = s.user_id
			left join status st on s.status_id = st.id
			left join problem p on s.problem_id = p.id
		group by u.id, p.id
	''')
	conn.execute('''alter table user_problem add column incorrect int''')
	conn.execute('''update user_problem
		set incorrect = (
			select sum(case when user_problem.soonest is null then 1 end)
			from submission s
				left join status st on s.status_id = st.id and st.name <> 'CORRECT'
			where user_problem.user_id = s.user_id and user_problem.problem_id = s.problem_id
		)
	''')
	conn.execute('''alter table user add column score integer''')
	conn.execute('''alter table user add column last_soonest integer''')
	conn.execute('''alter table user add column rank integer''')
	conn.execute('''update user
		set score = (
			select count(case when soonest is not null then 1 end)
			from user_problem up where up.user_id = user.id
		)
		, last_soonest = (
			select max(soonest)
			from user_problem up where up.user_id = user.id
		)
	''')
	conn.execute('''update user
		set rank = 1 + (select count(*) from user u where u.score > user.score)
	''')

def timeGrid(conn):
	date = conn.execute('''select now from contest''').fetchone()['now']
	s = ('Ranking last updated '
		'<script>document.write(new Date({utc}*1000).toLocaleString());</script>'
		).format(utc=time.mktime(date.timetuple()))
	return [[s]]

def rankingGrid(conn):
	grid = []

	contest = conn.execute('''select code from contest''').fetchone()

	row = []
	row.append('Rank')
	row.append('Name')
	row += (
		('<a href="/{c[code]}/problems/{p[code]}/">'
			'<font title="{p[name]}">{p[code]}</font>'
		'</a>').format(c=contest, p=problem)
		for problem
		in conn.execute('''select code, name from problem order by id''')
	)
	row.append('Score')
	grid.append(row)

	for user in conn.execute('''
			select id, username, name, score, rank
			from user where score > 0 order by score desc, last_soonest
		'''):

		row = []
		row.append('{u[rank]}'.format(u=user))
		row.append('<a href="/{c[code]}/users/{u[username]}/">{u[name]}</a>'.format(c=contest, u=user))
		for user_problem in conn.execute('''
				select p.code, pt.name type_name, up.best, up.fastest, up.soonest, up.incorrect
				from problem p
					left join user_problem up on p.id = up.problem_id and up.user_id = ?
					left join problem_type pt on p.problem_type_id = pt.id
				order by p.id
			''', (user['id'],)):

			if user_problem['soonest']:
				if user_problem['type_name'] == 'CLASSICAL':
					best_display = '{up[fastest]:.2f}s'.format(up=user_problem)
				else:
					best_display = '{up[best]:.0f}'.format(up=user_problem)
				row.append(
					('<a href="/{c[code]}/status/{up[code]},{u[username]}/">'
						'<script>'
							'var d = new Date({up[soonest]}*1000);'
							'document.write((d.getMonth()+1)+"/"+d.getDate()+"/"+(d.getFullYear()%1000));'
						'</script>'
						'<br/>'
						'{best_display}'
					'</a>'
					).format(c=contest, u=user, up=user_problem, best_display=best_display)
				)
			elif user_problem['incorrect']:
				row.append(
					('<a href="/{c[code]}/status/{up[code]},{u[username]}/">({up[incorrect]})</a>'
					).format(c=contest, u=user, up=user_problem)
				)
			else:
				row.append('')
		row.append('{u[score]}'.format(u=user))
		grid.append(row)

	return grid

def gridToString(grid):
	lines = []
	lines.append(str(len(grid[0])))
	lines += grid[0]
	lines.append(str(len(grid[1:])))
	for line in grid[1:]:
		lines += line
	lines.append('')
	return '\n'.join(lines)

if __name__ == '__main__':
	conn = create_db()

	in_file = os.fdopen(0, 'r') if len(sys.argv) == 1 else open(sys.argv[1], 'r')
	load_db(conn, in_file)
	in_file.close()

	calc_stats(conn)

	out_file = os.fdopen(6, 'w') if len(sys.argv) == 1 else sys.stdout
	out_file.write('2\n')
	out_file.write(gridToString(timeGrid(conn)))
	out_file.write(gridToString(rankingGrid(conn)))
	out_file.close()

	conn.close()
