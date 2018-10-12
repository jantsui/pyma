import datetime
import getopt
import sys
import pprint
from warnings import filterwarnings
import pymysql
import string
import configparser
import sqlparse
from sqlparse.sql import IdentifierList, Identifier
from sqlparse.tokens import Keyword, DML

filterwarnings('ignore', category = pymysql.Warning)

seq1="+"
seq2="<br/>"
seq3="</td><td>"

SYS_PARM_FILTER = (
    'BINLOG_CACHE_SIZE',
    'BULK_INSERT_BUFFER_SIZE',
    'HAVE_PARTITION_ENGINE',
    'HAVE_QUERY_CACHE',
    'INTERACTIVE_TIMEOUT',
    'JOIN_BUFFER_SIZE',
    'KEY_BUFFER_SIZE',
    'KEY_CACHE_AGE_THRESHOLD',
    'KEY_CACHE_BLOCK_SIZE',
    'KEY_CACHE_DIVISION_LIMIT',
    'LARGE_PAGES',
    'LOCKED_IN_MEMORY',
    'LONG_QUERY_TIME',
    'MAX_ALLOWED_PACKET',
    'MAX_BINLOG_CACHE_SIZE',
    'MAX_BINLOG_SIZE',
    'MAX_CONNECT_ERRORS',
    'MAX_CONNECTIONS',
    'MAX_JOIN_SIZE',
    'MAX_LENGTH_FOR_SORT_DATA',
    'MAX_SEEKS_FOR_KEY',
    'MAX_SORT_LENGTH',
    'MAX_TMP_TABLES',
    'MAX_USER_CONNECTIONS',
    'OPTIMIZER_PRUNE_LEVEL',
    'OPTIMIZER_SEARCH_DEPTH',
    'QUERY_CACHE_SIZE',
    'QUERY_CACHE_TYPE',
    'QUERY_PREALLOC_SIZE',
    'RANGE_ALLOC_BLOCK_SIZE',
    'READ_BUFFER_SIZE',
    'READ_RND_BUFFER_SIZE',
    'SORT_BUFFER_SIZE',
    'SQL_MODE',
    'TABLE_CACHE',
    'THREAD_CACHE_SIZE',
    'TMP_TABLE_SIZE',
    'WAIT_TIMEOUT'
) 

def is_subselect(parsed):
    if not parsed.is_group:
        return False
    for item in parsed.tokens:
        if item.ttype is DML and item.value.upper() == 'SELECT':
            return True
    return False

def extract_from_part(parsed):
    from_seen = False
    for item in parsed.tokens:
        #print(item.ttype,item.value
        if from_seen:
            if is_subselect(item):
                for x in extract_from_part(item):
                    yield x
            elif item.ttype is Keyword:
                raise StopIteration
            else:
                yield item
        elif item.ttype is Keyword and item.value.upper() == 'FROM':
            from_seen = True

def extract_table_identifiers(token_stream):
    for item in token_stream:
        if isinstance(item, IdentifierList):
            for identifier in item.get_identifiers():
                yield identifier.get_real_name()
        elif isinstance(item, Identifier):
            yield item.get_real_name()
        # It's a bug to check for Keyword here, but in the example
        # above some tables names are identified as keywords...
        elif item.ttype is Keyword:
            yield item.value

def extract_tables(p_sqltext):
    stream = extract_from_part(sqlparse.parse(p_sqltext)[0])
    return list(extract_table_identifiers(stream))

def f_find_in_list(myList,value):
    try: 
        for v in range(0,len(myList)): 
            if value==myList[v]: 
                return 1
        return 0
    except: 
        return 0

def f_get_parm(p_dbinfo):
    conn = pymysql.connect(host=p_dbinfo[0], user=p_dbinfo[1], passwd=p_dbinfo[2],db=p_dbinfo[3])
    cursor = conn.cursor()
    cursor.execute("select lower(variable_name),variable_value from INFORMATION_SCHEMA.GLOBAL_VARIABLES where upper(variable_name) in ('"+"','".join(list(SYS_PARM_FILTER))+"') order by variable_name")
    records = cursor.fetchall()
    cursor.close()
    conn.close()
    return records

def f_print_parm(p_parm_result):
    print("<p> SYSTEM PARAMETER </p><table border='1' width='100%'><tr>")
    status_title=('parameter_name','value')
    print("<th>")
    print(status_title[0].center(30))
    print("</th><th>",status_title[1].center(58))
    print("</th></tr>")

    for row in p_parm_result:
      print("<tr><td>",row[0].ljust(30))
      if 'size' in row[0]:
            if int(row[1])>=1024*1024*1024:
                print(seq3,(str(round(int(row[1])/1024/1024/1024,2))+' G').rjust(58),seq3)
            elif int(row[1])>=1024*1024:
                print(seq3,(str(round(int(row[1])/1024/1024,2))+' M').rjust(58),seq3)
            elif int(row[1])>=1024:
                print(seq3,(str(round(int(row[1])/1024,2))+' K').rjust(58),seq3)
            else:
                print(seq3,(row[1]+' B').rjust(58),seq3)
      else:
            print(seq3,row[1].rjust(58),seq3)
    print("</td></tr>")
    print("</table>")

def f_print_optimizer_switch(p_dbinfo):
    print("<p> OPTIMIZER SWITCH </p><table border='1' width='100%'><tr>")
    db = pymysql.connect(host=p_dbinfo[0], user=p_dbinfo[1], passwd=p_dbinfo[2],db=p_dbinfo[3])
    cursor = db.cursor()
    cursor.execute("select variable_value from INFORMATION_SCHEMA.GLOBAL_VARIABLES where upper(variable_name)='OPTIMIZER_SWITCH'")
    rows = cursor.fetchall()

    print("<th>",'switch_name'.center(40),)
    print("</th><th>",'value'.center(10),seq3)
    print("</th></tr>\n<tr>")
    for row in rows[0][0].split(','):
        print("<td>",row.split('=')[0].ljust(40),)
        print(seq3,row.split('=')[1].rjust(10),"</td>")
    print("</tr>")
    cursor.close()
    db.close()
    print("</table>")

def f_exec_sql(p_dbinfo,p_sqltext,p_option):
    results={}
    conn = pymysql.connect(host=p_dbinfo[0], user=p_dbinfo[1], passwd=p_dbinfo[2],db=p_dbinfo[3])
    cursor = conn.cursor()

    if f_find_in_list(p_option,'PROFILING'):
        cursor.execute("set profiling=1")
        cursor.execute("select ifnull(max(query_id),0) from INFORMATION_SCHEMA.PROFILING")
        records = cursor.fetchall()
        query_id=records[0][0] +2   #skip next sql

    if f_find_in_list(p_option,'STATUS'):
        #cursor.execute("select concat(upper(left(variable_name,1)),substring(lower(variable_name),2,(length(variable_name)-1))) var_name,variable_value var_value from INFORMATION_SCHEMA.SESSION_STATUS where variable_name in('"+"','".join(tuple(SES_STATUS_ITEM))+"') order by 1")
        cursor.execute("select concat(upper(left(variable_name,1)),substring(lower(variable_name),2,(length(variable_name)-1))) var_name,variable_value var_value from INFORMATION_SCHEMA.SESSION_STATUS order by 1")
        records = cursor.fetchall()
        results['BEFORE_STATUS']=dict(records)

    cursor.execute(p_sqltext)

    if f_find_in_list(p_option,'STATUS'):
        cursor.execute("select concat(upper(left(variable_name,1)),substring(lower(variable_name),2,(length(variable_name)-1))) var_name,variable_value var_value from INFORMATION_SCHEMA.SESSION_STATUS order by 1")
        records = cursor.fetchall()
        results['AFTER_STATUS']=dict(records)

    if f_find_in_list(p_option,'PROFILING'):
        cursor.execute("select STATE,DURATION,CPU_USER,CPU_SYSTEM,BLOCK_OPS_IN,BLOCK_OPS_OUT ,MESSAGES_SENT ,MESSAGES_RECEIVED ,PAGE_FAULTS_MAJOR ,PAGE_FAULTS_MINOR ,SWAPS from INFORMATION_SCHEMA.PROFILING where query_id="+str(query_id)+" order by seq")
        records = cursor.fetchall()
        results['PROFILING_DETAIL']=records

        cursor.execute("SELECT STATE,SUM(DURATION) AS Total_R,ROUND(100*SUM(DURATION)/(SELECT SUM(DURATION) FROM INFORMATION_SCHEMA.PROFILING WHERE QUERY_ID="+str(query_id)+"),2) AS Pct_R,COUNT(*) AS Calls,SUM(DURATION)/COUNT(*) AS R_Call FROM INFORMATION_SCHEMA.PROFILING WHERE QUERY_ID="+str(query_id)+" GROUP BY STATE ORDER BY Total_R DESC")
        records = cursor.fetchall()
        results['PROFILING_SUMMARY']=records

    cursor.close()
    conn.close()
    return results

def f_print_status(p_before_status,p_after_status):
    print("<p> SESSION STATUS (DIFFERENT) </p><table border='1' width='100%'><tr>")
    status_title=('status_name','before','after','diff')

    print("<th>",status_title[0].center(35),)
    print("</th><th>",status_title[1].center(15),)
    print("</th><th>",status_title[2].center(15),)
    print("</th><th>",status_title[3].center(15),"</th></tr>\n<tr><td>")
    
    for key in sorted(p_before_status.keys()):
        if p_before_status[key] != p_after_status[key]:
            print(key.ljust(35))
            print(seq3,p_before_status[key].rjust(15),)
            print(seq3,p_after_status[key].rjust(15),)
            print(seq3,str(float(p_after_status[key])-float(p_before_status[key])).rjust(15),"</td>")
    print("</tr>")
    print("</table>")
    
def f_print_time(p_starttime,p_endtime):
    print("<p> EXECUTE TIME </p>")
    print(timediff(p_starttime,p_endtime))

def f_print_profiling( p_profiling_detail , p_profiling_summary ):
    print("<p> SQL PROFILING(DETAIL)</p><table border='1' width='100%'><tr>")
    status_title=('state','duration','cpu_user','cpu_sys','bk_in','bk_out','msg_s','msg_r','p_f_ma','p_f_mi','swaps')
    print("<th>")
    print("</th><th>",status_title[0].center(30),)
    print("</th><th>",status_title[1].center(8),)
    print("</th><th>",status_title[2].center(8),)
    print("</th><th>",status_title[3].center(8),)
    print("</th><th>",status_title[4].center(8),)
    print("</th><th>",status_title[5].center(8),)
    print("</th><th>",status_title[6].center(8),)
    print("</th><th>",status_title[7].center(8),)
    print("</th><th>",status_title[8].center(8),)
    print("</th><th>",status_title[9].center(8),)
    print("</th><th>",status_title[10].center(8),seq3)
    print("</th></tr>\n<tr><td>")

    for row in p_profiling_detail:
        print(row[0].ljust(30))
        print(seq3,str(row[1]).rjust(8),)
        print(seq3,str(row[2]).rjust(8),)
        print(seq3,str(row[3]).rjust(8),)
        print(seq3,str(row[4]).rjust(8),)
        print(seq3,str(row[5]).rjust(8),)
        print(seq3,str(row[6]).rjust(8),)
        print(seq3,str(row[7]).rjust(8),)
        print(seq3,str(row[8]).rjust(8),)
        print(seq3,str(row[9]).rjust(8),)
        print(seq3,str(row[10]).rjust(8),"</td>")
    print("+--------------------------------+----------+----------+----------+----------+----------+----------+----------+----------+----------+----------+")
    print("bk_in:   block_ops_in")
    print("bk_out:  block_ops_out")
    print("msg_s:   message sent")
    print("msg_r:   message received")
    print("p_f_ma:  page_faults_major")
    print("p_f_mi:  page_faults_minor")
    print("<br/>")

    print("<p> SQL PROFILING(SUMMARY)</p><table border='1' width='100%'><tr>")
    status_title=('state','total_r','pct_r','calls','r/call')
    print("<th>")
    print("</th><th>",status_title[0].center(35),)
    print("</th><th>",status_title[1].center(15),)
    print("</th><th>",status_title[2].center(10),)
    print("</th><th>",status_title[3].center(5),)
    print("</th><th>",status_title[4].center(15),"</th>")
    print("</tr>\n<tr><td>")

    for row in p_profiling_summary:
        print(row[0].ljust(35))
        print(seq3,str(row[1]).rjust(15),)
        print(seq3,str(row[2]).rjust(10),)
        print(seq3,str(row[3]).rjust(5),)
        print(seq3,str(row[4]).rjust(15),"</td>")
    print("</tr>")
    print("</table>")
    
def f_get_sqlplan(p_dbinfo,p_sqltext):
    results={}
    db = pymysql.connect(host=p_dbinfo[0], user=p_dbinfo[1], passwd=p_dbinfo[2],db=p_dbinfo[3])
    cursor = db.cursor()
    cursor.execute("explain extended "+p_sqltext)
    records = cursor.fetchall()
    results['SQLPLAN']=records
    cursor.execute("show warnings")
    records = cursor.fetchall()
    results['WARNING']=records
    cursor.close()
    db.close()
    return results

def f_print_sqlplan(p_sqlplan,p_warning):
    plan_title=('id','select_type','table','type','possible_keys','key','key_len','ref','rows','filtered','Extra')

    print("<p> SQL PLAN </p><table border='1' width='100%'><tr>")
    print("<th>")
    print(plan_title[0].center(6))
    print("</th><th>",plan_title[1].center(16),)
    print("</th><th>",plan_title[2].center(10),)
    print("</th><th>",plan_title[3].center(10),)
    print("</th><th>",plan_title[4].center(20),)
    print("</th><th>",plan_title[5].center(10),)
    print("</th><th>",plan_title[6].center(10),)
    print("</th><th>",plan_title[7].center(10),)
    print("</th><th>",plan_title[8].center(10),)
    print("</th><th>",plan_title[9].center(10),)
    print("</th><th>",plan_title[10].center(10),"</th>")
    print("</tr>\n<tr><td>")
    for row in p_sqlplan:
        print(str(row[0]).rjust(6),)                # id
        print(seq3,row[1].ljust(16),)                    # select_type
        if not "NoneType" in str(type(row[2])):
            print(seq3,row[2].ljust(10),)                # table
        else:
            print(seq3,"NULL".ljust(10),)                # table
        if not "NoneType" in str(type(row[3])):
            print(seq3,row[3].ljust(10),)                # type
        else:
            print(seq3,"NULL".ljust(10),)                # type
        
        if not "NoneType" in str(type(row[4])):         # possible_keys
            print(seq3,row[4].ljust(20),)
        else:
            print(seq3,"NULL".ljust(20),)

        if not "NoneType" in str(type(row[5])):         # key
            print(seq3,row[5].ljust(10), )                   
        else:
            print(seq3,"NULL".ljust(10),)
        
        if not "NoneType" in str(type(row[6])):         # key_len
            print(seq3,row[6].ljust(10),)
        else:
            print(seq3,"NULL".ljust(10),)

        if not "NoneType" in str(type(row[7])):         # ref
            print(seq3,row[7].ljust(10),)                    
        else:
            print(seq3,"NULL".ljust(10),)

        print(seq3,str(row[8]).rjust(10),)               # rows

        print(seq3,str(row[9]).rjust(10),)               # rows

        if not "NoneType" in str(type(row[10])):        # Extra
            if not "float" in str(type(row[10])):
                print(seq3,row[10].ljust(10),)
            else:
              print(seq3,"float".ljust(10),)
        else:
            print(seq3,"NULL".ljust(10),)
        print("</td>")

    print("</tr>")
    print("</table>")

    print("<p> OPTIMIZER REWRITE SQL </p>")
    for row in p_warning:
        print(sqlparse.format(row[2],reindent=True, keyword_case='upper',strip_comments=True))
    print

def f_get_table(p_dbinfo,p_sqltext):
    r_tables=[]
    db = pymysql.connect(host=p_dbinfo[0], user=p_dbinfo[1], passwd=p_dbinfo[2],db=p_dbinfo[3])
    cursor = db.cursor()
    cursor.execute("explain "+p_sqltext)
    rows = cursor.fetchall ()
    for row in rows:
        table_name = row[2]
        if '<' in table_name:
            continue
        if len(r_tables)==0:
            r_tables.append(table_name)
        elif f_find_in_list(r_tables,table_name) == -1:
            r_tables.append(table_name)
    cursor.close()
    db.close()
    return r_tables

def f_print_tableinfo(p_dbinfo,p_tablename):
    plan_title=('table_name','engine','format','table_rows','avg_row','total_mb','data_mb','index_mb')
    db = pymysql.connect(host=p_dbinfo[0], user=p_dbinfo[1], passwd=p_dbinfo[2],db=p_dbinfo[3])
    cursor = db.cursor()
    stmt = "select engine,row_format as format,table_rows,avg_row_length as avg_row,round((data_length+index_length)/1024/1024,2) as total_mb,round((data_length)/1024/1024,2) as data_mb,round((index_length)/1024/1024,2) as index_mb from information_schema.tables where table_schema='"+p_dbinfo[3]+"' and table_name='"+p_tablename+"'"
    cursor.execute(stmt)
    rows = cursor.fetchall ()
    print("<th>",plan_title[0].center(15),)
    print("</th><th>",plan_title[1].center(10),)
    print("</th><th>",plan_title[2].center(10),)
    print("</th><th>",plan_title[3].center(10),)
    print("</th><th>",plan_title[4].center(10),)
    print("</th><th>",plan_title[5].center(10),)
    print("</th><th>",plan_title[6].center(10),)
    print("</th><th>",plan_title[7].center(10),"</th></tr>\n<tr>")
    print("<td>")
    for row in rows:
        print(p_tablename.ljust(15))
        print(seq3,row[0].ljust(10),)
        print(seq3,row[1].ljust(10),)    
        print(seq3,str(row[2]).rjust(10),) 
        print(seq3,str(row[3]).rjust(10),)
        print(seq3,str(row[4]).rjust(10),)                    
        print(seq3,str(row[5]).rjust(10),)                    
        print(seq3,str(row[6]).rjust(10),"</td>")
    print("</tr>")
    cursor.close()
    db.close()
    print("</table>")

def f_print_indexinfo(p_dbinfo,p_tablename):
    plan_title=('index_name','non_unique','seq_in_index','column_name','collation','cardinality','nullable','index_type')
    db = pymysql.connect(host=p_dbinfo[0], user=p_dbinfo[1], passwd=p_dbinfo[2],db=p_dbinfo[3])
    cursor = db.cursor()
    stmt = "select index_name,non_unique,seq_in_index,column_name,collation,cardinality,nullable,index_type from information_schema.statistics where table_schema='"+p_dbinfo[3]+"' and table_name='"+p_tablename+"' order by 1,3"
    cursor.execute(stmt)
    rows = cursor.fetchall ()
    if len(rows)>0:
        print("<th>",plan_title[0].center(15),)
        print("</th><th>",plan_title[1].center(15),)
        print("</th><th>",plan_title[2].center(15),)
        print("</th><th>",plan_title[3].center(15),)
        print("</th><th>",plan_title[4].center(15),)
        print("</th><th>",plan_title[5].center(15),)
        print("</th><th>",plan_title[6].center(15),)
        print("</th><th>",plan_title[7].center(15),"</th></tr>\n<tr>")
        print("<td>")
        for row in rows:
            print(row[0].ljust(15))
            print(seq3,str(row[1]).rjust(15),)
            print(seq3,str(row[2]).rjust(15),)
            print(seq3,str(row[3]).rjust(15),)
            print(seq3,str(row[4]).rjust(15),)
            print(seq3,str(row[5]).rjust(15),)
            print(seq3,str(row[6]).rjust(15),)
            print(seq3,str(row[7]).rjust(15),"</td>")
        print("</tr>")
    cursor.close()
    db.close()
    print("</table>")

def f_get_mysql_version(p_dbinfo):
    db = pymysql.connect(host=p_dbinfo[0], user=p_dbinfo[1], passwd=p_dbinfo[2],db=p_dbinfo[3])
    cursor = db.cursor()
    cursor.execute("select @@version")
    records = cursor.fetchall ()
    cursor.close()
    db.close()
    return records[0][0]

def f_print_title(p_dbinfo,p_mysql_version,p_sqltext):
    print('*'*100)
    print('*','MySQL SQL Tuning Tools v1.0 (by hanfeng)'.center(96),'*')
    print('*'*100)

    print
    print("<p> BASIC INFORMATION </p>")
    title=('server_ip','user_name','db_name','db_version')
    print("+----------------------+------------+------------+------------+")
    print(seq2,title[0].center(20),)
    print(seq2,title[1].center(10),)
    print(seq2,title[2].center(10),)
    print(seq2,title[3].center(10),seq2)
    print("+----------------------+------------+------------+------------+")
    print(seq2,p_dbinfo[0].center(20),)
    print(seq2,p_dbinfo[1].center(10),)
    print(seq2,p_dbinfo[3].center(10),)
    print(seq2,p_mysql_version.center(10),seq2)
    print("+----------------------+------------+------------+------------+")
    print("<br/>")
    print("<p> ORIGINAL SQL TEXT </p>")
    print(sqlparse.format(p_sqltext,reindent=True, keyword_case='upper'))
    print("<br/>")

'''
def f_print_table(p_value,p_option):  #p_option "(key-n => title,max_len,align_value)"
    for k in p_option.keys():
        v = p_option[k]
        print("+",
        print(int(v.split(',')[1])*"-",
    print("+"
    
    for k in p_option.keys():
        v = p_option[k]
        print("|",
        print(v.split(',')[0].center(int(v.split(',')[0])-2),
    print("|",

    for k in p_option.keys():
        v = p_option[k]
        print("+",
        print(int(v.split(',')[1])*"-",
    print("+"

    for row in p_value:
        k=0
        for col in row:
            k+=1
            print("|",
            if p_option[k].split(',')[2]=='l':
                print(col.ljust(p_option[k].split(',')[1]),
            elif p_option[k].split(',')[2]=='r':
                print(col.rjust(p_option[k].split(',')[1]),
            else
                print(col.center(p_option[k].split(',')[1]),
            print("|",

    for k in p_option.keys():
        v = p_option[k]
        print("+",
        print(int(v.split(',')[1])*"-",
    print("+"
'''

def timediff(timestart, timestop):
        t  = (timestop-timestart)
        time_day = t.days
        s_time = t.seconds
        ms_time = t.microseconds / 1000000
        usedtime = int(s_time + ms_time)
        time_hour = usedtime / 60 / 60
        time_minute = (usedtime - time_hour * 3600 ) / 60
        time_second =  usedtime - time_hour * 3600 - time_minute * 60
        time_micsecond = (t.microseconds - t.microseconds / 1000000) / 1000

        retstr = "%d day %d hour %d minute %d second %d microsecond "  %(time_day, time_hour, time_minute, time_second, time_micsecond)
        return retstr

if __name__=="__main__":
    dbinfo=["","","",""]  #dbhost,dbuser,dbpwd,dbname
    sqltext=""
    option=[]
    config_file=""
    mysql_version=""

    opts, args = getopt.getopt(sys.argv[1:], "p:s:")
    for o,v in opts:
        if o == "-p":
            config_file = v
        elif o == "-s":
            sqltext = v

    config = configparser.ConfigParser()
    config.read("mysql_tuning.ini")
#    config.readfp(open(config_file,"rb"))
    dbinfo[0] = config.get("database","server_ip")
    dbinfo[1] = config.get("database","db_user")
    dbinfo[2] = config.get("database","db_pwd")
    dbinfo[3] = config.get("database","db_name")

    mysql_version = f_get_mysql_version(dbinfo)
    
    f_print_title(dbinfo,mysql_version,sqltext)

    if config.get("option","sys_parm")=='ON':
        parm_result = f_get_parm(dbinfo)
        f_print_parm(parm_result)
        f_print_optimizer_switch(dbinfo)

    if config.get("option","sql_plan")=='ON':
        sqlplan_result = f_get_sqlplan(dbinfo,sqltext)
        f_print_sqlplan(sqlplan_result['SQLPLAN'],sqlplan_result['WARNING'])

    if config.get("option","obj_stat")=='ON':
        print("<p> OBJECT STATISTICS </p><table border='1' width='100%'><tr>")
        for table_name in extract_tables(sqltext):
            f_print_tableinfo(dbinfo,table_name)
            f_print_indexinfo(dbinfo,table_name)
        print

    if config.get("option","ses_status")=='ON':
        option.append('STATUS')

    if config.get("option","sql_profile")=='ON':
        option.append('PROFILING')

    if config.get("option","ses_status")=='ON' or config.get("option","sql_profile")=='ON':
        starttime = datetime.datetime.now()
        exec_result = f_exec_sql(dbinfo,sqltext,option)
        endtime = datetime.datetime.now()

        if config.get("option","ses_status")=='ON':
            f_print_status(exec_result['BEFORE_STATUS'],exec_result['AFTER_STATUS'])

        if config.get("option","sql_profile")=='ON':
            f_print_profiling(exec_result['PROFILING_DETAIL'],exec_result['PROFILING_SUMMARY'])

        f_print_time(starttime,endtime)