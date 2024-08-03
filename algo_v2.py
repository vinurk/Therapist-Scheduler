import mysql.connector as mc
import requests
from datetime import datetime, timedelta
import random



def find_schedule(MYSQL_HOST,MYSQL_USER,MYSQL_PASSWORD,MYSQL_DB):

    db = mc.connect(host=MYSQL_HOST, user=MYSQL_USER,
                password=MYSQL_PASSWORD, database=MYSQL_DB)
    curs = db.cursor() 

    # Google distance matrix api
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    KEY = ""                   # API Key

    # The following dictionaries are going to hold the data taken from mysql database
    patient_details = {}
    therapists_details = {}
    job_id_det = {}

    # This dictionary will be used later to get the finalt schedule of each therapist
    therapists_patients_pair = {}


    # This function gets the data from the databse and stores it in the above dictionaries
    def read_db():
        # curs.execute("SELECT * FROM patients JOIN therapy_plans ON patients.ID = therapy_plans.ID ORDER BY patients.ID")
        # print(curs.fetchall())
        curs.execute("SELECT * FROM patients")
        patients_raw = curs.fetchall()

        for row in patients_raw:
            patient_details[row[0]] = {"name": row[1], "address": row[2], "availability": list(
                map(str.strip, row[3].split(','))), "reqd_prf": []}

        curs.execute("SELECT * FROM therapy_plans")
        therapy_plans = curs.fetchall()

        for row in therapy_plans:
            patient_details[row[0]]['reqd_prf'] = list(
                map(str.strip, row[1].split(',')))

        curs.execute("SELECT * FROM job_ids")
        job_ids = curs.fetchall()

        for row in job_ids:
            job_id_det[row[0]] = row[1]

        curs.execute("SELECT * FROM therapists")
        therapists_raw = curs.fetchall()

        curs.execute("SELECT * FROM therapist_availability")
        therapist_availability = curs.fetchall()

        for row in therapists_raw:
            therapists_details[row[0]] = {
                "name": row[1], "address": row[2], "job_id": row[3], 'availability': {}}

        for row in therapist_availability:
            therapists_details[row[0]]['availability'].update(
                {'time_from': row[3], 'time_to': row[4], 'days': list(map(str.strip, row[2].split(',')))})


    # This function is used to get the distance between origins and destination
    # When multiple origins and/or destinations is given the api gives back a matrix of the distances
    def get_distance(origin: str, dest: str):

        params = {
            "origins": origin,
            "destinations": dest,
            "units": "imperial",
            "key": KEY
        }

        response = requests.request("GET", url, params=params)
        matrix = []
        for row in response.json()['rows']:
            n_row = []
            for col in row['elements']:
                n_row.append(col['duration']['value'])
            matrix.append(n_row)
        return matrix


    # This was just a function to produce a matrix like the one produced by google api, so that
    # i can use this funciton while testing, and it does not waste the api resources
    def make_matrix(param: str, param1: str, val,rand=False):
        num = len(param.split('|'))-1
        num1 = len(param1.split('|'))-1
        l = []
        for r in range(num):
            row = []
            for c in range(num1):
                if rand:
                    row.append(random.randint(200, 2000))
                else:
                    row.append(val)
            l.append(row)
        return l


    read_db()

    # Here the therapists_patients_pair dictionary is used
    # In this following process, a list of patients taken from the therapy_plans table are mapped to the
    # Corresponding therapists and days and a list of patients for the next week is created and added to the dictionary with
    # the therapist id as the key
    for p_id, p_det in patient_details.items():

        found = 0
        for t_id, t_det in therapists_details.items():
            # print(t_det)
            if (t_det['job_id'] in p_det['reqd_prf']):
                if t_id not in therapists_patients_pair:
                    therapists_patients_pair[t_id] = {'patients': [], 'days': [
                        {day: []} for day in t_det['availability']['days']]}
                therapists_patients_pair[t_id]['patients'].append(p_id)
                for day in p_det['availability']:
                    for av_day in therapists_patients_pair[t_id]['days']:
                        if day in av_day:
                            therapists_patients_pair[t_id]['days'][therapists_patients_pair[t_id]['days'].index(
                                av_day)][day].append(p_id)
                            break
                found += 1
                if found == len(p_det['reqd_prf']):
                    pass


    # This is the final process that makes the final schedule
    therapy_plan = {}
    p_therpay_plan = {}
    api_limit = 10  # This is the maximum number of origin or destination the api can take in one api call
    # For example: the api can only take 10 origin and 10 destinations at once which produces a matrix of 10x10 which will have 100 elements in the matrix, which is the limit of the api

    unique_profession_limit = 2
    paitient_week_visit_limit = 3

    for t_id, det in therapists_patients_pair.items():
        
        google_params = []
        pids: list = therapists_patients_pair[t_id]['patients']

        # pids, has the list of patients for the whole week, first we need to find the distances between each patient and therapist
        # Let's consider the pids has 17 patients
        # As said earlier the api can take only ten origin and destination per call
        # So, we need to get the final matrix of 17 x 17 by dividing the pids list into 10+7 elements
        # Then first the matrix for first 10 matrix is obtained and then the rest 7 elements is obtained
        # But right now only the parameters are created for api and the it is not yet called.

        pids.insert(0, 't-'+t_id)
        u_lim = 0
        num = (len(pids)//10) + (1 if len(pids) % 10 != 0 else 0)
        l_lim = api_limit if len(pids) > api_limit else len(pids)
        param = ''

        for _ in range(num):
            
            for pid in pids[u_lim:l_lim]:
                if 't-' in pid:
                    addr = therapists_details[pid.split('-')[-1]]['address']
                else:
                    addr = patient_details[pid]['address']
                param += addr+"|"
            u_lim = l_lim
            l_lim = (l_lim+api_limit) if len(pids)-l_lim > api_limit else len(pids)
            google_params.append(param)
            param = ''

        # this is used to make a empty matrix of size len(pids) x len(pids) filled with zeroes
        
        mat = make_matrix('a|'*(len(pids)), 'a|'*(len(pids)), 0)

        # This whole process is actually calling the api and
        # It is a way to add up all the separate matrices into one final matrix
        # ie. if len(pids) was 17 then first a 10x10 matrix was created by the api call, then 7 x 7 matrix will be created and
        # then a 7 x 10 and  10 x 7 and 7 x 7 matrices will be created and all these matriced will  be added together to form 17 x 17 matrix

        # Instead of doing the above process we could just take one origin and one destination at once, then the code will be much simpler, but it has a few problems
        # 1. If the len(pids) was 17 then we have to make api calls that is equal to 17 x 17= 289 api calls, which is a huge number of api calls when compared to the above process
        # 2. I actually tried this and  it takes much much longer because eaach api call atleast 1 second to return some value, hence almost 289 seconds will be spent on making the distance matrix

        # So here the first method is used to make the distance matrix
        row, col, offset_r, offset_c = 0, 0, 0, 0
        lim = 0
        diff = 3
        mat_count = 0
        i = 0
        while i < len(google_params):
            main = google_params[i]
            s_i =0
            while s_i< i+1:
                sub_mat = get_distance(main, google_params[s_i])
                if mat!=lim:
                    sub_mat_T = [[sub_mat[j][i] for j in range(len(sub_mat))] for i in range(len(sub_mat[0]))]
                
                if mat_count==lim:
                    for r in range(len(sub_mat)):
                        for c in range(len(sub_mat[0])):
                            mat[offset_r+r][offset_c+c] = sub_mat[r][c]
                    old_r = 0
                    old_c = 0

                    offset_r += len(sub_mat)
                    offset_c += len(sub_mat)

                    lim+=diff
                    diff+=2
                    mat_count+=1
                
                else:
                    temp_r = offset_r
                    temp_c = old_c

                    for r in range(len(sub_mat)):
                        for c in range(len(sub_mat[0])):
                            mat[temp_r+r][temp_c+c] = sub_mat[r][c]
                    
                    temp_r = old_r
                    temp_c = offset_c

                    for r in range(len(sub_mat_T)):
                        for c in range(len(sub_mat_T[0])):
                            mat[temp_r+r][temp_c+c] = sub_mat_T[r][c]

                    mat_count+=2
                    if mat_count!=lim:
                        old_c+=len(sub_mat[0])
                        old_r+=len(sub_mat_T)
                s_i+=1

        
            i+=1

        # This is the end of making the distance matrix

        # This is example matrix of size 16 x 16  the distance matrix produced by the above process.
        # mat = [[float('inf'), 857, 791, 775, 693, 759, 772, 915, 584, 697, 609, 932, 1142, 745, 453, 797],
        #        [827, float('inf'), 154, 290, 279, 281, 309, 221,642, 362, 416, 286, 998, 266, 945, 228],
        #        [763, 159, float('inf'), 227, 216, 218, 246, 297,578, 276, 345, 366, 932, 148, 879, 69],
        #        [776, 296, 230, float('inf'), 126, 70, 77, 249,479, 349, 399, 256, 838, 375, 780, 291],
        #        [653, 252, 185, 116, float('inf'), 108, 131, 222, 448, 265, 342, 278, 805, 360, 752, 234],
        #        [759, 290, 224, 61, 120, float('inf'), 80, 242, 462, 332, 384, 292, 822, 366, 769, 276],
        #        [747, 314, 248, 83, 144, 81, float('inf'), 266, 471, 343, 387, 314, 804, 405, 754, 279],
        #        [867, 221, 301, 235, 213, 226, 254, float('inf'), 661, 478, 526, 182, 893, 410, 955, 374],
        #        [598, 685, 618, 520, 491, 509, 494, 695, float('inf'), 588, 492, 649, 1028, 722, 722, 596],
        #        [690, 348, 269, 331, 274, 316, 319, 458, 573,float('inf'), 153, 543, 1011, 310, 958, 203],
        #        [609, 416, 345, 399, 342, 384, 387, 526, 492,153, float('inf'), 587, 994, 350, 942, 276],
        #        [932, 286, 366, 256, 278, 292, 314, 182, 649,543, 574, float('inf'), 723, 467, 888, 424],
        #        [1142, 998, 932, 838, 805, 822, 804, 893, 1028,1011, 1042, 793, float('inf'), 1041, 1048, 927],
        #        [745, 266, 148, 375, 360, 366, 405, 410, 722,310, 360, 471, 1012, float('inf'), 961, 126],
        #        [453, 945, 879, 780, 752, 769, 754, 955, 722,958, 923, 916, 948, 988, float('inf'), 874],
        #        [797, 228, 69, 291, 234, 276, 279, 374, 596, 203, 233, 435, 886, 115, 835, float('inf')]]
        
        mat_copy = mat.copy()
        t_avail_time_from = therapists_details[t_id]['availability']['time_from']
        t_avail_time_to = therapists_details[t_id]['availability']['time_to']
        time_zero = datetime.strptime("00:00", "%H:%M")
        time_from = datetime.strptime(t_avail_time_from, "%H:%M")
        time_to = datetime.strptime(t_avail_time_to, "%H:%M")
        time_diff = (time_to - time_from).total_seconds()

        # Now the following process solves the TSP
        # Since there is no exact solution to TSP, i have used the "nearest house" approach
        # Here for each day, first the nearest house to therapist is taken and then from there the next nearest house is taken
        # and the schedule for each day is created
        chosen = []
        left_out = []
        for day in therapists_details[t_id]['availability']['days']:
            mat = mat_copy
            for d in therapists_patients_pair[t_id]['days']:
                if day in d:
                    p_day_list = d[day]
            for c in chosen:
                if c in p_day_list:
                    p_day_list.remove(c)
            time = 0
            t_time = 90*60
            plan = {}
            mat_r = 0
            while len(p_day_list) > 0:
                min = float('inf')
                p_day_ind, mat_c = 0, 0
                while p_day_ind < len(p_day_list):
                    mat_c = pids.index(p_day_list[p_day_ind])
                    if mat[mat_r][mat_c] < min:
                        min = mat[mat_r][mat_c]
                    p_day_ind += 1

                time += t_time+min
                if time <= time_diff:
                    ele = pids[mat[mat_r].index(min)]
                    cont = True

                    if ele in p_therpay_plan:
                        if (p_therpay_plan[ele][day]!='') or (p_therpay_plan[ele]['other_det']['total'] == paitient_week_visit_limit) or (p_therpay_plan[ele]['other_det']['u_prfs'].count(therapists_details[t_id]['job_id'])==unique_profession_limit):
                            cont=False
                                
                    if cont:
                        plan[ele] = time-t_time + \
                            (time_from-time_zero).total_seconds()
                        chosen.append(ele)
                        if ele not in p_therpay_plan:
                            p_therpay_plan[ele] = {
                                'Mo': '', 'Tu': '', 'We': '', 'Th': '', 'Fr': '', 'other_det': {'total':0,'u_prfs':[]}}
                        p_therpay_plan[ele][day] += t_id+"-" + str(time-t_time+(time_from-time_zero).total_seconds())
                        p_therpay_plan[ele]['other_det']['total']+=1
                        p_therpay_plan[ele]['other_det']['u_prfs'].append(therapists_details[t_id]['job_id'])

                        p_day_list.remove(ele)
                else:
                    break

                mat_r = mat[mat_r].index(min)
                for row in mat:
                    row[mat_r] = float('inf')

            if len(p_day_list) > 0:
                for p in p_day_list:
                    if p not in left_out:
                        left_out.append(p)

            if t_id not in therapy_plan:
                therapy_plan[t_id] = {}
            therapy_plan[t_id].update({day: plan})



    # Uploading the schedule to mysql:

    curs.execute("DELETE FROM therapist_schedule")
    db.commit()

    for t_id, sch in therapy_plan.items():
        query = """INSERT INTO therapist_schedule (ID, Therapist_name) VALUES (%s,%s)"""
        curs.execute(query, (t_id, therapists_details[t_id]['name']))
        for day_sch, p in sch.items():
            pid_s = ''
            for p_id, time in p.items():
                pid_s += p_id+'-'
            pid_s = pid_s[:len(pid_s)-1]
            query = f"UPDATE therapist_schedule SET {day_sch} = (%s) WHERE ID=(%s)"
            curs.execute(query, (pid_s, t_id))
            db.commit()


    curs.execute("DELETE FROM patient_schedule")
    db.commit()
    for p_id, p_sch in p_therpay_plan.items():
        query = """INSERT INTO patient_schedule (ID, Patient_Name) VALUES (%s,%s)"""
        curs.execute(query, (p_id, patient_details[p_id]['name']))
        for day, t_id_plus_time in p_sch.items():
            if day!='other_det':
                query = f"UPDATE patient_schedule SET {day} = (%s) WHERE ID=(%s)"
                temp = t_id_plus_time.split(',')
                for ele in temp:
                    t = ele.split('-')

                    if t[0] != '':
                        formated_time = str(timedelta(seconds=float(t[1])))
                        t[1] = formated_time
                        temp[temp.index(ele)] = '-'.join(t)
                temp = ','.join(temp)
                curs.execute(query, (temp[:len(temp)-1], p_id))
                db.commit()


    curs.execute("DELETE FROM left_out_patients")
    db.commit()
    for id in left_out:
        query = """INSERT INTO left_out_patients (ID) VALUES (%s)"""
        curs.execute(query,(id,))
        db.commit()


# This was the slower method to get the distance between two patients or one patient and one therapist

# for t_id,pts in therapists_patients_pair.items():
#     # print(t_id)
#     nodes:list = pts['patients']
#     nodes.insert(0,t_id)
#     for r_id in nodes:
#         row = []
#         if nodes.index(r_id)==0:
#             orig_addr = therapists_details[r_id]['address']
#         else:
#             orig_addr = patient_details[r_id]['address']

#         for c_id in nodes:
#             if nodes.index(c_id)==0:
#                 dest_addr = therapists_details[c_id]['address']
#             else:
#                 dest_addr = patient_details[c_id]['address']
#             print(get_distance(orig_addr,dest_addr))
#         therapists_patients_pair[t_id]['distance_matrix'].append(row)
