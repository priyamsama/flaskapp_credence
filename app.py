from datetime import date
from functools import wraps
import os
import re
from flask import render_template, make_response
from weasyprint import HTML
import tempfile
from dotenv import load_dotenv
from flask import Flask, flash, render_template, redirect, request, session, url_for
from flask_mysqldb import MySQL
from MySQLdb import IntegrityError
from MySQLdb.cursors import DictCursor
from werkzeug.security import check_password_hash

from config import Config

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)
mysql = MySQL(app)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if session.get('user_id') is None:
            return redirect(url_for('login'))
        return view(*args, **kwargs)

    return wrapped_view


def fetch_all(query, params=()):
    cur = mysql.connection.cursor(DictCursor)
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
        valid_env_user = username == env_username and password == env_password


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
    patients= fetch_all('SELECT * from patients ORDER BY created_at DESC')
    return render_template('patient_menu.html',patients=patients)


@app.route('/patient/register', methods=['GET', 'POST'])
@login_required
def register_patient():
    if request.method == 'POST':
        patient_id = request.form['patient_id'].strip().upper()
        patient_name = request.form['patient_name'].strip()
        age_str = request.form['age'].strip()
        gender = request.form['gender']
        number = request.form['contact_number'].strip()

        def render_error(msg):
            flash(msg, 'error')
            submitted = {
                'patient_id': patient_id,
                'patient_name': patient_name,
                'age': age_str,
                'gender': gender,
                'contact_number': number
            }
            return render_template('patient_register.html', patient=submitted, mode='create')

        # 1. Check required fields
        if not patient_name or not patient_id or not age_str or not gender or not number:
            return render_error('All fields are required.')

        # 2. Patient ID format checking
        if not re.match(r'^P\d{6}$', patient_id):
            return render_error('Patient ID must follow the format P000001, P000002 … P999999.')

        # 3. NEW: Age Validation
        try:
            age = int(age_str)
            if age < 0 or age > 120:
                return render_error('Age must be a realistic number between 0 and 120.')
        except ValueError:
            return render_error('Age must be a valid whole number.')

        # 4. NEW: Contact Number Validation (Ensures exactly 10 digits)
        if not re.match(r'^\d{10}$', number):
            return render_error('Contact number must be exactly 10 digits long.')

        # 5. Duplicate Patient ID check 
        existing_id = fetch_one(
            'SELECT patient_id FROM patients WHERE patient_id = %s', (patient_id,)
        )
        if existing_id:
            return render_error(f'Patient ID "{patient_id}" already exists.')

        # 6. Database Insertion
        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                INSERT INTO patients
                (patient_id, patient_name, age, gender, contact_number)
                VALUES (%s, %s, %s, %s, %s)
            """, (patient_id, patient_name, age, gender, number))
            mysql.connection.commit()
            flash('Patient registered successfully.', 'success')
            return redirect(url_for('register_patient'))
        except Exception as e:
            mysql.connection.rollback()
            return render_error('An unexpected error occurred during registration.')
        finally:
            cur.close()

    return render_template('patient_register.html', patient=None, mode='create')


@app.route('/patient/update', methods=['GET', 'POST'])
@login_required
def patient_update():
    patient_fields = {
        'patient_name': 'Patient Name',
        'age': 'Age',
        'gender': 'Gender',
        'contact_number': 'Contact Number',
    }

    if request.method == 'POST':
        patient_id = request.form.get('patient_id', '').strip().upper()
        update_field = request.form.get('update_field', '').strip()
        update_value = request.form.get('update_value', '').strip()

        def render_error(msg):
            flash(msg, 'error')
            patient_ids = fetch_all("""
                SELECT patient_id, patient_name
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

        if not patient_id or not update_field or not update_value:
            return render_error('Patient ID, update field, and update value are required.')

        if not re.match(r'^P\d{6}$', patient_id):
            return render_error('Patient ID must follow the format P000001, P000002 ... P999999.')

        if update_field not in patient_fields:
            return render_error('Invalid patient field selected.')

        existing_patient = fetch_one('SELECT patient_id FROM patients WHERE patient_id = %s', (patient_id,))
        if not existing_patient:
            return render_error('Patient was not found.')

        if update_field == 'age':
            try:
                val = int(update_value)
                if val < 0 or val > 120:
                    return render_error('Age must be a realistic number between 0 and 120.')
            except ValueError:
                return render_error('Age must be a valid whole number.')

        if update_field == 'gender' and update_value not in ['Male', 'Female', 'Other']:
            return render_error('Gender must be Male, Female, or Other.')

        if update_field == 'contact_number' and not re.match(r'^\d{10}$', str(update_value)):
            return render_error('Contact number must be exactly 10 digits long.')

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
        mysql.connection.commit() # here the db changes permenantly saved without commit changes stay in memory
        cur.close() # releases the database resources
        flash('Patient updated successfully.', 'success')
        return redirect(url_for('patient_update'))

    return render_template('patient_register.html', patient=selected_patient, mode='edit')


@app.route('/sample')
@login_required
def sample():
    return render_template('sample_menu.html')


@app.route('/sample/register', methods=['GET', 'POST'])
@login_required
def register_sample():
    if request.method == 'POST':
        sample_id          = request.form['sample_id'].strip().upper()
        patient_id         = request.form['patient_id'].strip()
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

        # 1. Required fields 
        if not sample_id or not patient_id or not sample_type or not test or not collection_date or not referring_doctor or not referring_hospital:
            return render_error('All fields are required.')

        #  2. Sample ID format: S001 
        if not re.match(r'^S\d{6}$', sample_id):
            return render_error('Sample ID must follow the format S000001, S000002 … S999999.')

        #  3. Patient must exist in the database 
        patient = fetch_one(
            'SELECT patient_id FROM patients WHERE patient_id = %s', (patient_id,)
        )
        if not patient:
            return render_error('Selected patient does not exist.')

        # 4. Sample type whitelist 
        if sample_type not in ['Blood', 'Swab', 'Tissue']:
            return render_error('Invalid sample type.')

        #  5. Date must not be in the future 
        try:
            if date.fromisoformat(collection_date) > date.today():
                return render_error('Collection date cannot be in the future.')
        except ValueError:
            return render_error('Invalid date format.')

        #  6. Duplicate Sample ID check 
        existing = fetch_one(
            'SELECT sample_id FROM samples WHERE sample_id = %s', (sample_id,)
        )
        if existing:
            return render_error(f'Sample ID "{sample_id}" already exists.')

        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                INSERT INTO samples (sample_id, patient_id, sample_type, test, collection_date, referring_doctor, referring_hospital)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (sample_id, patient_id, sample_type, test, collection_date, referring_doctor, referring_hospital))
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
        'sample_type': 'Sample Type',
        'test': 'Test',
        'collection_date': 'Collection Date',
        'referring_doctor': 'Referring Doctor',
        'referring_hospital': 'Referring Hospital',
    }
    def get_dropdown_data():
        samples = fetch_all("""
            SELECT s.sample_id, p.patient_name
            FROM samples s
            JOIN patients p ON p.patient_id = s.patient_id
            ORDER BY s.sample_id
        """)
        patients = fetch_all("""
            SELECT patient_id, patient_name
            FROM patients
            ORDER BY patient_id
        """)
        return samples, patients


    if request.method == 'POST':
        sample_id = request.form.get('sample_id', '').strip().upper()
        update_field = request.form.get('update_field', '').strip()
        update_value = request.form.get('update_value', '').strip()

        if not sample_id or not update_field or not update_value:
            flash(" All fields are required ! ",'error')
        elif not re.match(r'^S\d{6}$',sample_id):
            flash(" Sample ID must follow the format S000001...S999999",'error')
        
        else:
            # Check if sample exists in database
            sample_check = fetch_one('SELECT sample_id FROM samples WHERE sample_id = %s', (sample_id,))
            if not sample_check:
                flash('Sample was not found.', 'error')
                
            # Check patient validity if updating patient_id
            elif update_field == 'patient_id' and not fetch_one('SELECT patient_id FROM patients WHERE patient_id = %s', (update_value,)):
                flash('Selected patient does not exist.', 'error')
                
            # Check sample type dropdown values
            elif update_field == 'sample_type' and update_value not in ['Blood', 'Swab', 'Tissue']:
                flash('Sample type must be Blood, Swab, or Tissue.', 'error')
                
            # Check date
            elif update_field == 'collection_date' and update_value > str(date.today()):
                flash('Collection date cannot be in the future.', 'error')
                
            # Check that text fields aren't completely blanked out
            elif update_field in ('referring_doctor', 'referring_hospital', 'test') and not update_value:
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

        sample_ids = fetch_all("SELECT s.sample_id, p.patient_name FROM samples s JOIN patients p ON p.patient_id = s.patient_id ORDER BY s.sample_id")
        patient_ids = fetch_all("SELECT patient_id, patient_name FROM patients ORDER BY patient_id")
        
        return render_template(
            'sample_update.html',
            sample_fields=sample_fields, sample_ids=sample_ids, patient_ids=patient_ids,
            sample_id=sample_id, update_field=update_field, update_value=update_value
        )

    # 4. Handle standard GET request (initial page load)
    sample_ids = fetch_all("SELECT s.sample_id, p.patient_name FROM samples s JOIN patients p ON p.patient_id = s.patient_id ORDER BY s.sample_id")
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
        # getting form ddata 
        patient_id         = request.form['patient_id'].strip()
        sample_type        = request.form['sample_type'].strip()
        test               = request.form['test'].strip()
        collection_date    = request.form['collection_date'].strip()
        referring_doctor   = request.form['referring_doctor'].strip()
        referring_hospital = request.form['referring_hospital'].strip()

        submitted_sample={
        'sample_id':sample_id,
        'patient_id':patient_id,
        'sample_type': sample_type,
        'test': test,
        'collection_date':collection_date,
        'referring_doctor': referring_doctor,
        'referring_hospital':referring_hospital
        }
        
        
        if not (patient_id and sample_id and test and collection_date and referring_doctor and referring_hospital):
            flash("All fields are required !",'error')
            patients = fetch_all('SELECT patient_id, patient_name FROM patients ORDER BY patient_name')
            return render_template('sample_register.html',patients=patients,sample=submitted_sample, mode="edit")
        elif collection_date > str(date.today()):
            flash("Collection date cannot be in future ! ", 'error')
            patients = fetch_all('SELECT patient_id, patient_name FROM patients ORDER BY patient_name')
            return render_template('sample_register.html',patients=patients,sample=submitted_sample, mode="edit")
        else:
            
            try:
                cur = mysql.connection.cursor()
                cur.execute("""
                UPDATE samples
                SET patient_id = %s, sample_type = %s, test = %s,
                    collection_date = %s, referring_doctor = %s, referring_hospital = %s
                WHERE sample_id = %s
                """, (patient_id, sample_type, test, collection_date, referring_doctor, referring_hospital, sample_id))
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

@app.route('/patient/search', methods=['GET', 'POST'])
@login_required
def patient_search():
    results = []
    query = ''
    searched = False

    if request.method == 'POST':
        searched = True
        query = request.form.get('query', '').strip()

        sql = """
            SELECT patient_id, patient_name, age, gender, contact_number, created_at
            FROM patients
        """
        params = []

        if query:
            search_value = f'%{query}%'
            sql += """
                WHERE patient_id LIKE %s
                   OR patient_name LIKE %s
                   OR contact_number LIKE %s
            """
            params.extend([search_value, search_value, search_value])

        sql += " ORDER BY created_at DESC"
        results = fetch_all(sql, tuple(params))

    return render_template(
        'patient_search.html',
        results=results,
        query=query,
        searched=searched
    )


@app.route('/sample/search', methods=['GET', 'POST'])
@login_required
def sample_search():
    results = []
    query = ''
    start_date = ''
    end_date = ''
    searched = False

    if request.method == 'POST':
        searched = True
        query = request.form.get('query', '').strip()
        start_date = request.form.get('start_date', '').strip()
        end_date = request.form.get('end_date', '').strip()

        sql = """
            SELECT s.sample_id, s.sample_type, s.collection_date, s.test, s.referring_doctor, s.referring_hospital, p.patient_id, p.patient_name
            FROM samples s
            JOIN patients p ON p.patient_id = s.patient_id
        """
        conditions = []
        params = []

        if query:
            search_value = f'%{query}%'
            conditions.append("""
                (s.sample_id LIKE %s OR p.patient_id LIKE %s OR p.patient_name LIKE %s OR s.sample_type LIKE %s)
            """)
            params.extend([search_value, search_value, search_value,search_value])

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

    return render_template(
        'search.html', 
        results=results, 
        query=query, 
        start_date=start_date, 
        end_date=end_date,
        searched=searched
    )

@app.route('/report')
@login_required
def report():
    return render_template('report_menu.html')


@app.route('/report')
@login_required
def reporting():
    cursor = mysql.connection.cursor(DictCursor)
    cursor.execute('''
        SELECT r.report_id, r.patient_id, p.patient_name, r.report_status,
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
    if request.method == 'POST':
        report_id = request.form['report_id'].strip().upper()
        patient_id = request.form['patient_id'].strip()
        draft_text = request.form['draft_text']
        comments = request.form['comments']
        status = request.form['report_status']

        submitted_report = {
            'report_id': report_id,
            'patient_id': patient_id,
            'draft_text': draft_text,
            'comments': comments,
            'report_status': status
        }
        
        

        if not report_id:
            flash("Invalid report id", 'error')
            patients = fetch_all('SELECT patient_id FROM patients') 
            return render_template('reporting.html', patients=patients)
        elif not (patient_id):
            flash('invalid patient id ','error')
            return render_template('reporting.html', patients=patients)
        elif not re.match(r'^R\d{6}$', report_id):
            flash("Invalid Report ID, must follow this format R000001,... R999999", 'error')
            return render_template(
            'reporting.html',
            patients=patients,
            report=submitted_report,
            mode='create'
            )
          
        else:
            existing = fetch_one(
                        "SELECT report_id FROM patient_report WHERE report_id=%s",
                        (report_id,))
            if existing:
                flash("Report ID already exists.", "error")
                return render_template(
                    'reporting.html'
                )
            cur = mysql.connection.cursor()
            cur.execute(
                """
                INSERT INTO patient_report (report_id, patient_id, draft_text, comments, report_status)
                VALUES (%s,%s,%s,%s,%s)
                """, 
                (report_id, patient_id, draft_text, comments, 'Pending')
            )
            mysql.connection.commit()
            cur.close()
            flash("The report saved successfully!",'success')
            return redirect(url_for('reporting'))
    cur = mysql.connection.cursor()
    cur.execute("SELECT patient_id FROM patients")
    patients = cur.fetchall()
    cur.close()

    return render_template(
    'reporting.html',
    patients=patients,
    report=None,
    mode='create'
    )
@app.route('/report/<report_id>/edit', methods=['GET', 'POST'])
@login_required 
def edit_report(report_id):
    report = fetch_one('SELECT * FROM patient_report WHERE report_id = %s', (report_id,))
    if not report:
        flash('Report was not found.', 'error')
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
        'reporting.html',
        patients=patients,
        report=report,
        mode='edit'
    )
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
        patient_id = request.form.get('patient_id', '').strip()
        created_at = request.form.get('created_at', '').strip()
        
        sql = """
            SELECT 
                pr.report_id,
                p.patient_id,
                p.patient_name,
                s.sample_type,
                s.collection_date,
                s.test,
                s.referring_doctor,
                s.referring_hospital
            FROM patient_report pr
            INNER JOIN patients p ON pr.patient_id = p.patient_id
            INNER JOIN samples s ON p.patient_id = s.patient_id
        """
        
        # 2. Track conditions dynamically
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
            
        
    return render_template(
        'report_search.html',
        results=results,
        report_id=report_id,
        patient_id=patient_id,
        created_at=created_at,
        searched=searched
    )


@app.route('/report/download/<report_id>', methods=['POST'])
@login_required
def draft_print(report_id):
    patient_id = request.form['patient_id']
    draft_text = request.form['draft_text']
    comments = request.form['comments']
    status = request.form['report_status']

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE patient_report
        SET patient_id = %s, draft_text = %s, comments = %s, report_status = %s, update_at = NOW()
        WHERE report_id = %s
    """, (patient_id, draft_text, comments, status, report_id))
    mysql.connection.commit()
    cur.close()

    # Render HTML
    html = render_template(
        'report_pdf.html',
        report_id=report_id,
        patient_id=patient_id,
        draft_text=draft_text,
        comments=comments,
        status=status
    )

    # Generate PDF
    pdf = HTML(string=html).write_pdf()

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=report_{report_id}.pdf'

    return response




if __name__ == '__main__':
    app.run(debug=True)


