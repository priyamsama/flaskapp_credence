import re
import random
import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException 
from datetime import date, datetime
from functools import wraps
from flask import render_template, make_response
from weasyprint import HTML
from dotenv import load_dotenv
from flask import Flask, flash, render_template, redirect, request, session, url_for
from flask_mysqldb import MySQL
from MySQLdb import IntegrityError
from MySQLdb.cursors import DictCursor
from werkzeug.security import check_password_hash

from config import Config

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config) # this line loads the configuration from config.py, including database credentials and secret key
mysql = MySQL(app) #here its initialiize the mysql with flask app, so we can use  mysql.connection to interact with the db, by flask_mysqldb library

#this fuction act as a gate keeper for the routes which requieres login

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if session.get('user_id') is None:
            return redirect(url_for('login'))
        return view(*args, **kwargs)

    return wrapped_view

# these are the helper fuction fetch data fromt the db instead of repeating it 

def fetch_all(query, params=()):
    cur = mysql.connection.cursor(DictCursor) #this line make each row comes as the form of dictionary 

    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    return rows


def fetch_one(query, params=()):
    cur = mysql.connection.cursor(DictCursor)
    cur.execute(query, params)
    row = cur.fetchone()
    cur.close()
    return row

# these functions used to generate unique ids for patient samples and reports


def generate_patient_id():
    row = fetch_one("SELECT patient_id FROM patients ORDER BY LENGTH(patient_id) DESC, patient_id DESC LIMIT 1")
    if not row:
        return 'P000001'
    last_num = int(row['patient_id'][1:])
    return f'P{last_num + 1:06d}'

def generate_sample_id():
    row = fetch_one("SELECT sample_id FROM samples ORDER BY sample_id DESC LIMIT 1")
    if not row:
        return 'S000001'
    last_num = int(row['sample_id'][1:])
    return f'S{last_num + 1:06d}'

def generate_report_id():
    row = fetch_one("SELECT report_id FROM patient_report ORDER BY report_id DESC LIMIT 1")
    if not row:
        return 'R000001'
    last_num = int(row['report_id'][1:])
    return f'R{last_num + 1:06d}'

'''def generate_sample_name():
    while True:

        random_number= random.randint(000000,999999)
        sample_name=f'SC{random_number}'

        #chekig whether have an existing sample  name
        existing_samples=fetch_one('select * from samples where sample_name = %s ',(sample_name))

        if not existing_samples:
            return sample_name'''


# this is the main route to the app login 
@app.route('/')
def index():
    if session.get('user_id') is not None:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        user = None
        try:
            user = fetch_one("""
                SELECT user_id, username, password_hash
                FROM users
                WHERE username = %s AND is_active = TRUE
            """, (username,))
        except Exception:
            mysql.connection.rollback()

        env_username = app.config['ADMIN_USERNAME']
        env_password = app.config['ADMIN_PASSWORD']
        valid_database_user = user and check_password_hash(user['password_hash'], password)
        valid_env_user = username == env_username and password == env_password # we only used the env use for the login credential



        if valid_database_user or valid_env_user:
            session.clear()
            session['user_id'] = user['user_id'] if user else 0
            session['username'] = username
            return redirect(url_for('dashboard'))

        flash('Invalid username or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    stats = {
        'patients': fetch_one('SELECT COUNT(*) AS total FROM patients')['total'],
        'samples': fetch_one('SELECT COUNT(*) AS total FROM samples')['total'],
    }
    recent_samples = fetch_all("""
        SELECT s.sample_id, s.sample_type, s.collection_date, s.test, s.referring_doctor, s.referring_hospital, p.patient_id, p.patient_name
        FROM samples s
        JOIN patients p ON p.patient_id = s.patient_id
        ORDER BY s.created_at DESC
        LIMIT 5
    """)
    return render_template('index.html', stats=stats, recent_samples=recent_samples)


@app.route('/patient')
@login_required
def patient():
    return render_template('patient_menu.html')


@app.route('/patient/register', methods=['GET', 'POST'])
@login_required
def register_patient():
    if request.method == 'POST':
        patient_id   = generate_patient_id()
        patient_name = request.form['patient_name'].strip().capitalize()
        nic          = request.form['id'].strip()
        age_str      = request.form['age'].strip()
        gender       = request.form['gender']
        number       = request.form['contact_number'].strip()

        def render_error(msg):
            flash(msg, 'error')
            submitted = {
                'patient_name': patient_name,
                'id':           nic,
                'age':          age_str,
                'gender':       gender,
                'contact_number': number
            }
            return render_template('patient_register.html', patient=submitted, mode='create')

        if not patient_name or not age_str or not gender or not number:
            return render_error('All fields are required.')

        try:
            age = int(age_str)
            if age < 0 or age > 120:
                return render_error('Age must be between 0 and 120.')
        except ValueError:
            return render_error('Age must be a valid whole number.')

        if not re.match(r'^\d{10}$', number):
            return render_error('Contact number must be exactly 10 digits.')
        
        existing_patient = fetch_one("""
            SELECT id, contact_number 
            FROM patients 
            WHERE id = %s OR contact_number = %s
        """, (nic, number))

        if existing_patient:
            
            if existing_patient[0] == nic:
                return render_error('A patient with this NIC already exists.')
            else:
                return render_error('A patient with this contact number already exists.')

        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                INSERT INTO patients (patient_id, patient_name, age, gender, contact_number, id)
                VALUES (%s, %s, %s, %s, %s,%s)
            """, (patient_id, patient_name, age, gender, number, nic))
            mysql.connection.commit()
            flash('Patient registered successfully.', 'success')
            return redirect(url_for('register_patient'))
        except IntegrityError:
            mysql.connection.rollback()
            return render_error('A patient with this NIC already exists.')
        except Exception as e:
            mysql.connection.rollback()
            print(e)
            return render_error('An unexpected error occurred during registration.')
        finally:
            cur.close()

    return render_template('patient_register.html', patient=None, mode='create')

@app.route('/patient/update', methods=['GET', 'POST'])
@login_required
def patient_update():
    patient_fields = {
        'patient_name': 'Patient Name',
        'id':'NIC',
        'age': 'Age',
        'gender': 'Gender',
        'contact_number': 'Contact Number',
    }

    if request.method == 'POST':
        patient_id = request.form.get('patient_id', '').strip().upper()
        update_field = request.form.get('update_field', '').strip()
        update_value = request.form.get('update_value', '').strip().capitalize()

        def render_error(msg):
            flash(msg, 'error')
            patient_ids = fetch_all("""
                SELECT patient_id, patient_name,id 
                FROM patients
                ORDER BY patient_id
            """)
            return render_template(
                'patient_update.html',
                patient_fields=patient_fields,
                patient_ids=patient_ids,
                patient_id=patient_id,
                update_field=update_field,
                update_value=update_value
            )
        update_value = update_value.strip()

        if not patient_id or not update_field or not update_value:
            return render_error('Patient ID, update field, and update value are required.')

        if update_field not in patient_fields:
            return render_error('Invalid patient field selected.')


        if update_field == 'age':
            try:
                val = int(update_value)
                if val < 0 or val > 120:
                    return render_error('Age must be a realistic number between 0 and 120.')
            except ValueError:
                return render_error('Age must be a valid whole number.')

        elif update_field == 'gender' and update_value not in ['Male', 'Female', 'Other']:
            return render_error('Gender must be Male, Female, or Other.')

        elif update_field in ['contact_number', 'Contact Number']:
            if not re.match(r'^\d{10}$', update_value):
                return render_error('Contact number must be exactly 10 digits long.')
        elif update_field in ['id', 'NIC']:
            if not re.match(r'^\d{10}$', update_value):
                return render_error('enter a valid nic .')


        cur = mysql.connection.cursor()
        cur.execute(
            f"UPDATE patients SET {update_field} = %s WHERE patient_id = %s",
            (update_value, patient_id)
        )
        mysql.connection.commit()
        cur.close()
        flash(f'{patient_fields[update_field]} updated successfully.', 'success')
        return redirect(url_for('patient_update'))

    patient_ids = fetch_all("""
        SELECT patient_id, patient_name
        FROM patients
        ORDER BY patient_id
    """)
    return render_template(
        'patient_update.html',
        patient_fields=patient_fields,
        patient_ids=patient_ids
    )
'''
@app.route('/patient/<patient_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_patient(patient_id):
    selected_patient = fetch_one('SELECT * FROM patients WHERE patient_id = %s', (patient_id,))
    if not selected_patient:
        flash('Patient was not found.', 'error')
        return redirect(url_for('patient_update'))

    if request.method == 'POST':
        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE patients
            SET patient_name = %s, age = %s, gender = %s, contact_number = %s
            WHERE patient_id = %s
        """, (
            request.form['patient_name'].strip(),
            request.form['age'],
            request.form['gender'],
            request.form['contact_number'].strip(),
            patient_id,
        ))
        mysql.connection.commit() 
        cur.close()
        flash('Patient updated successfully.', 'success')
        return redirect(url_for('patient_update'))

    return render_template('patient_register.html', patient=selected_patient, mode='edit')
'''
@app.route('/sample')
@login_required
def sample():
    return render_template('sample_menu.html')


@app.route('/sample/register', methods=['GET', 'POST'])
@login_required
def register_sample():
    if request.method == 'POST':
        sample_id = generate_sample_id()
        patient_id         = request.form['patient_id'].strip()
        sample_name        = request.form['sample_name'].strip()
        sample_type        = request.form['sample_type'].strip()
        test               = request.form['test'].strip()
        collection_date    = request.form['collection_date'].strip()
        referring_doctor   = request.form['referring_doctor'].strip()
        referring_hospital = request.form['referring_hospital'].strip()

        def render_error(msg):
            flash(msg, 'error')
            submitted = {
                'sample_id': sample_id,
                'patient_id': patient_id,
                'sample_name': sample_name,
                'sample_type': sample_type,
                'test': test,
                'collection_date': collection_date,
                'referring_doctor': referring_doctor,
                'referring_hospital': referring_hospital
            }
            patients = fetch_all('SELECT patient_id, patient_name FROM patients ORDER BY patient_name')
            return render_template(
                'sample_register.html',
                today=date.today().isoformat(),
                patients=patients,
                sample=submitted,
                mode='create'
            )

        if not patient_id or not sample_name or not sample_type or not test or not collection_date or not referring_doctor or not referring_hospital:
            return render_error('All fields are required.')

        # Check unique sample_name
        existing_sample_name = fetch_one('SELECT sample_id FROM samples WHERE sample_name = %s', (sample_name,))
        if existing_sample_name:
            return render_error('A sample with this sample name already exists.')
        
        patient = fetch_one(
            'SELECT patient_id FROM patients WHERE patient_id = %s', (patient_id,)
        )
        if not patient:
            return render_error('Selected patient does not exist.')

        if sample_type not in ['Blood', 'Swab', 'Tissue']:
            return render_error('Invalid sample type.')

        try:
            if date.fromisoformat(collection_date) > date.today():
                return render_error('Collection date cannot be in the future.')
        except ValueError:
            return render_error('Invalid date format.')

        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                INSERT INTO samples (sample_id, patient_id, sample_name, sample_type, test, collection_date, referring_doctor, referring_hospital)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (sample_id, patient_id, sample_name, sample_type, test, collection_date, referring_doctor, referring_hospital))
            mysql.connection.commit()
            flash('Sample registered successfully.', 'success')
            return redirect(url_for('register_sample'))
        except IntegrityError:
            mysql.connection.rollback()
            return render_error('A database error occurred. Please try again.')
        finally:
            cur.close()

    patients = fetch_all('SELECT patient_id, patient_name FROM patients ORDER BY patient_name')
    return render_template(
        'sample_register.html',
        today=date.today().isoformat(),
        patients=patients,
        sample=None,
        mode='create'
    )

@app.route('/sample/update', methods=['GET', 'POST'])
@login_required
def sample_update():
    sample_fields = {
        'patient_id': 'Patient ID',
        'sample_name': 'Sample Name',
        'sample_type': 'Sample Type',
        'test': 'Test',
        'collection_date': 'Collection Date',
        'referring_doctor': 'Referring Doctor',
        'referring_hospital': 'Referring Hospital',
    }
    

    if request.method == 'POST':
        sample_id = request.form.get('sample_id', '').strip().upper()
        update_field = request.form.get('update_field', '').strip()
        update_value = request.form.get('update_value', '').strip()

        if not sample_id or not update_field or not update_value:
            flash(" All fields are required ! ",'error')
        elif not re.match(r'^S\d{6}$',sample_id):
            flash(" Sample ID must follow the format S000001...S999999",'error')
        
        else:
            sample_check = fetch_one('SELECT sample_id FROM samples WHERE sample_id = %s', (sample_id,))
            if not sample_check:
                flash('Sample was not found.', 'error')
                
            elif update_field == 'patient_id' and not fetch_one('SELECT patient_id FROM patients WHERE patient_id = %s', (update_value,)):
                flash('Selected patient does not exist.', 'error')
                
            elif update_field == 'sample_type' and update_value not in ['Blood', 'Swab', 'Tissue']:
                flash('Sample type must be Blood, Swab, or Tissue.', 'error')
                
            elif update_field == 'collection_date' and update_value > str(date.today()):
                flash('Collection date cannot be in the future.', 'error')
                
            elif update_field == 'sample_name' and fetch_one('SELECT sample_id FROM samples WHERE sample_name = %s AND sample_id != %s', (update_value, sample_id)):
                flash('A sample with this sample name already exists.', 'error')
                
            elif update_field in ('referring_doctor', 'referring_hospital', 'test', 'sample_name') and not update_value:
                flash(f'{sample_fields[update_field]} cannot be empty.', 'error')
                
            else:
                cur = mysql.connection.cursor()
                cur.execute(
                    f"UPDATE samples SET {update_field} = %s WHERE sample_id = %s",
                    (update_value, sample_id)
                )
                mysql.connection.commit()
                cur.close()
                
                flash(f'{sample_fields[update_field]} updated successfully.', 'success')
                return redirect(url_for('sample_update'))

        sample_ids = fetch_all("SELECT s.sample_id, s.sample_name, p.patient_name FROM samples s JOIN patients p ON p.patient_id = s.patient_id ORDER BY s.sample_id")
        patient_ids = fetch_all("SELECT patient_id, patient_name FROM patients ORDER BY patient_id")
        
        return render_template(
            'sample_update.html',
            sample_fields=sample_fields, sample_ids=sample_ids, patient_ids=patient_ids,
            sample_id=sample_id, update_field=update_field, update_value=update_value
        )

    sample_ids = fetch_all("SELECT s.sample_id, s.sample_name, p.patient_name FROM samples s JOIN patients p ON p.patient_id = s.patient_id ORDER BY s.sample_id")
    patient_ids = fetch_all("SELECT patient_id, patient_name FROM patients ORDER BY patient_id")
    
    return render_template(
        'sample_update.html',
        sample_fields=sample_fields,
        sample_ids=sample_ids,
        patient_ids=patient_ids
    )


@app.route('/sample/<sample_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_sample(sample_id):
    selected_sample = fetch_one('SELECT * FROM samples WHERE sample_id = %s', (sample_id,))
    if not selected_sample:
        flash('Sample was not found.', 'error')
        return redirect(url_for('sample_update'))

    if request.method == 'POST':
        patient_id         = request.form['patient_id'].strip()
        sample_name        = request.form['sample_name'].strip()
        sample_type        = request.form['sample_type'].strip()
        test               = request.form['test'].strip()
        collection_date    = request.form['collection_date'].strip()
        referring_doctor   = request.form['referring_doctor'].strip()
        referring_hospital = request.form['referring_hospital'].strip()

        submitted_sample={
        'sample_id':sample_id,
        'patient_id':patient_id,
        'sample_name': sample_name,
        'sample_type': sample_type,
        'test': test,
        'collection_date':collection_date,
        'referring_doctor': referring_doctor,
        'referring_hospital':referring_hospital
        }
        
        if not (patient_id and sample_name and test and collection_date and referring_doctor and referring_hospital):
            flash("All fields are required !",'error')
            patients = fetch_all('SELECT patient_id, patient_name FROM patients ORDER BY patient_name')
            return render_template('sample_register.html',patients=patients,sample=submitted_sample, mode="edit")
        elif collection_date > str(date.today()):
            flash("Collection date cannot be in future ! ", 'error')
            patients = fetch_all('SELECT patient_id, patient_name FROM patients ORDER BY patient_name')
            return render_template('sample_register.html',patients=patients,sample=submitted_sample, mode="edit")
        
        # Check unique sample_name
        existing_sample_name = fetch_one('SELECT sample_id FROM samples WHERE sample_name = %s AND sample_id != %s', (sample_name, sample_id))
        if existing_sample_name:
            flash('A sample with this sample name already exists.', 'error')
            patients = fetch_all('SELECT patient_id, patient_name FROM patients ORDER BY patient_name')
            return render_template('sample_register.html', patients=patients, sample=submitted_sample, mode='edit')
        
        else:
            try:
                cur = mysql.connection.cursor()
                cur.execute("""
                UPDATE samples
                SET patient_id = %s, sample_name = %s, sample_type = %s, test = %s,
                    collection_date = %s, referring_doctor = %s, referring_hospital = %s
                WHERE sample_id = %s
                """, (patient_id, sample_name, sample_type, test, collection_date, referring_doctor, referring_hospital, sample_id))
                mysql.connection.commit()
                cur.close()

                flash('Sample updated successfully.', 'success')
                return redirect(url_for('sample_update'))
            
            except IntegrityError:
                flash('The selected patient is invalid ! ','error')
                patients = fetch_all('SELECT patient_id, patient_name FROM patients ORDER BY patient_name')
                return render_template('sample_register.html', patients=patients, sample=submitted_sample, mode='edit')

            
    patients = fetch_all('SELECT patient_id, patient_name FROM patients ORDER BY patient_name')
    return render_template(
            'sample_register.html',
            patients=patients,
            sample=selected_sample,
            mode='edit'
        )

@app.route('/patient/search', methods=['GET'])
@login_required
def patient_search():
    return render_template('patient_search.html')



@app.route('/patient/search/results', methods=['GET', 'POST'])
@login_required
def patient_search_results():
    query = request.form.get('patient_name', '').strip()
    results = []
    if query:
        search_value = f'%{query}%'
        results = fetch_all(
            "SELECT * FROM patients WHERE patient_name LIKE %s OR id LIKE %s ORDER BY patient_name",
            (search_value, search_value)
        )
    return render_template('patient_search_results.html', results=results, query=query)
@app.route('/sample/search', methods=['GET'])
@login_required
def sample_search():
    return render_template('search.html')


@app.route('/sample/search/results', methods=['POST'])
@login_required
def sample_search_results():
    query       = request.form.get('query',       '').strip()
    sample_type = request.form.get('sample_type', '').strip()
    start_date  = request.form.get('start_date',  '').strip()
    end_date    = request.form.get('end_date',     '').strip()

    sql = """
        SELECT s.sample_id, s.sample_name, s.sample_type, s.collection_date, s.test,
               s.referring_doctor, s.referring_hospital,
               p.patient_id, p.patient_name
        FROM samples s
        JOIN patients p ON p.patient_id = s.patient_id
    """
    conditions = []
    params = []

    if query:
        search_value = f'%{query}%'
        conditions.append("""
            (s.sample_id LIKE %s OR s.sample_name LIKE %s OR p.patient_id LIKE %s OR p.patient_name LIKE %s OR s.sample_type LIKE %s)
        """)
        params.extend([search_value, search_value, search_value, search_value, search_value])

    if sample_type:
        conditions.append("s.sample_type = %s")
        params.append(sample_type)

    if start_date:
        conditions.append("s.collection_date >= %s")
        params.append(start_date)

    if end_date:
        conditions.append("s.collection_date <= %s")
        params.append(end_date)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY s.collection_date DESC"
    results = fetch_all(sql, tuple(params))

    return render_template('sample_search_results.html',
        results=results,
        query=query,
        sample_type=sample_type,
        start_date=start_date,
        end_date=end_date)


@app.route('/report')
@login_required
def report():
    return render_template('report_menu.html')


@app.route('/report/list')
@login_required
def reporting():
    cursor = mysql.connection.cursor(DictCursor)
    cursor.execute('''
        SELECT r.report_id, r.sample_id, p.patient_name,
               r.created_at, r.update_at
        FROM patient_report r
        JOIN patients p ON r.patient_id = p.patient_id
        ORDER BY r.update_at DESC
    ''')
    reports = cursor.fetchall()
    cursor.close()
    return render_template('report_list.html', reports=reports)


@app.route('/report/create', methods=['GET', 'POST'])
@login_required
def create_report():
    samples = fetch_all('SELECT sample_id, sample_name, sample_type, patient_id FROM samples ORDER BY sample_id')
    now = datetime.now()
    formatted_now = now.strftime("%A, %B %d, %Y - %I:%M %p")

    if request.method == 'POST':
        raw_input     = request.form.get('sample_id', '').strip()
        comments      = request.form.get('comments', '').strip()
        signature_choice = request.form.get('signature', 'no')

        def render_error(msg):
            flash(msg, 'error')
            return render_template('report_create.html', samples=samples, report=None, mode='create')

        if not raw_input:
            return render_error('Please select a sample.')

        # Resolve by sample_id first, then fall back to sample_name
        sample = fetch_one('SELECT * FROM samples WHERE sample_id = %s', (raw_input,))
        if not sample:
            sample = fetch_one('SELECT * FROM samples WHERE sample_name = %s', (raw_input,))
        if not sample:
            return render_error('Sample not found.')

        # Now we always have the real sample_id from the DB row
        sample_id  = sample['sample_id']
        patient_id = sample['patient_id']

        patient = fetch_one('SELECT * FROM patients WHERE patient_id = %s', (patient_id,))
        if not patient:
            return render_error('Patient not found.')

        existing = fetch_one(
            'SELECT report_id FROM patient_report WHERE sample_id = %s', (sample_id,)
        )

        if existing:
            report_id = existing['report_id']
            cur = mysql.connection.cursor()
            try:
                cur.execute("""
                    UPDATE patient_report
                    SET comments = %s, update_at = NOW()
                    WHERE report_id = %s
                """, (comments, report_id))
                mysql.connection.commit()
            except Exception as e:
                mysql.connection.rollback()
                print(e)
            finally:
                cur.close()
        else:
            report_id = generate_report_id()
            cur = mysql.connection.cursor()
            try:
                cur.execute("""
                    INSERT INTO patient_report (report_id, patient_id, sample_id, comments)
                    VALUES (%s, %s, %s, %s)
                """, (report_id, patient_id, sample_id, comments))
                mysql.connection.commit()
            except Exception as e:
                mysql.connection.rollback()
                print(e)
                return render_error('An unexpected error occurred while saving.')
            finally:
                cur.close()

        with_signature = (signature_choice == 'yes')
        import os
        project_dir = os.path.dirname(os.path.abspath(__file__))
        signature_img_path = 'file:///' + os.path.join(project_dir, 'static', 'images', 'signature.png').replace('\\', '/')
        html = render_template(
            'report_pdf.html',
            with_signature=with_signature,
            signature_img_path=signature_img_path,
            report_id=report_id,
            patient=patient,
            sample=sample,
            comments=comments,
            current_time=formatted_now
        )
        try:
            pdf = HTML(string=html, base_url=project_dir).write_pdf()
            response = make_response(pdf)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename={sample_id}_report.pdf'
            return response
        except Exception as e:
            print(f"WeasyPrint PDF generation error: {e}")
            flash('Error generating PDF report.', 'error')
            return render_template('report_create.html', samples=samples, report=None, mode='create')

    return render_template('report_create.html', samples=samples, report=None, mode='create')


# report edit for particular report id
'''@app.route('/report/<report_id>/edit', methods=['GET', 'POST'])
@login_required 
def edit_report(report_id):
    report = fetch_one('SELECT * FROM patient_report WHERE report_id = %s', (report_id,))
    if not report:
        flash('Report was not found.', 'error')
        return redirect(url_for('reporting'))
    patient = fetch_one('SELECT patient_id, patient_name FROM patients WHERE patient_id = %s', (report['patient_id'],))
    if not patient:
        flash('Patient was not found.', 'error')
        return redirect(url_for('reporting'))

    if request.method == 'POST':
        patient_id = request.form['patient_id'].strip()
        draft_text = request.form['draft_text']
        comments = request.form['comments']
        status = request.form['report_status']
        report_id = report['report_id']

        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE patient_report
            SET patient_id = %s, draft_text = %s, comments = %s, report_status = %s, update_at = NOW()
            WHERE report_id = %s
        """, (patient_id, draft_text, comments, status, report_id))
        mysql.connection.commit()
        cur.close()

        flash('Report updated successfully.', 'success')
        return redirect(url_for('reporting'))

    patients = fetch_all('SELECT patient_id, patient_name FROM patients ORDER BY patient_name')
    return render_template(
        'report_edit.
                <a href="{{ url_for('report') }}" class="{% if request.path.startswith('/report') %}active{% endif %}">html',
        patients=patients,
        report=report,
        mode='edit'
    )
'''
@app.route('/report/search', methods=['GET', 'POST'])
@login_required
def search_report():
    results = []
    report_id = ''
    patient_id = ''
    created_at = ''
    searched = False

    if request.method == 'POST':
        searched = True
        report_id = request.form.get('report_id', '').strip()
        patient_id = request.form.get('patient_name', '').strip()
        created_at = request.form.get('created_at', '').strip()
        
        sql = """
            SELECT pr.*, s.patient_id, s.sample_type, p.patient_name
                FROM patient_report pr
                JOIN samples s ON pr.sample_id = s.sample_id
                JOIN patients p ON s.patient_id = p.patient_id
                WHERE pr.report_id = %s
        """
        
        
        conditions = []
        params = []

        if report_id:
            conditions.append("pr.report_id LIKE %s")
            params.append(f'%{report_id}%')

        if patient_id:
            conditions.append("p.patient_id LIKE %s")
            params.append(f'%{patient_id}%')

        if created_at:
            conditions.append("DATE(pr.created_at) = %s")
            params.append(created_at)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
            #sql += " ORDER BY pr.created_at DESC"
        results = fetch_all(sql, tuple(params))
    print("Results:", results)

    with_signature = request.args.get("signature") == "yes"
    return render_template(
        'report_search.html',
        results=results,
        report_id=report_id,
        patient_id=patient_id,
        created_at=created_at,
        searched=searched,
    )


if __name__ == '__main__':
    app.run(debug=True)


