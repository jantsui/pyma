import re

Com_commit_S = """Com_commit""" #4140
Com_rollback_S = """Com_rollback""" #4197
#执行查询的总次
Questions_S = """Queries""" #4415
#服务器已经运行的时间（以秒为单位）
my_Uptime = """Uptime""" #4470

f = open("H:\\IOE\\监控脚本\\resdb-01\\20181016_resdb-01_check.txt","r",encoding="utf-8")

Com_rollback_T = 0 
for line in f:
    if Com_commit_S in line:
        Com_commit_T=int( re.search("(?P<name>\D+)(?P<value>\d+)",line).group("value"))
        print(Com_commit_T)
    if  re.search( Com_rollback_S , line ):
        if Com_rollback_T==0:
            Com_rollback_T=int(re.search("(?P<name>\D+)(?P<value>\d+)",line).group("value"))
            print(Com_rollback_T)
    if Questions_S in line:
        Questions_T=int(re.search("(?P<name>\D+)(?P<value>\d+)",line).group("value"))
        print(Questions_T)
    if my_Uptime in line:
        Uptime_T=int(re.search("(?P<name>\D+)(?P<value>\d+)",line).group("value"))
        print(Uptime_T)

m_QPS = str(round(Questions_T/Uptime_T, 5))
print ("QPS(每秒查询次数): " + m_QPS) 
TPS = str(round((Com_commit_T + Com_rollback_T)/Uptime_T, 5))
print ("TPS(每秒执行的事务数量): " + TPS)

