from datetime import date
from functools import wraps
import os
import re

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
            request.form['patient_name'].strip(), #strip removes the extra spaces
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

    if request.method == 'POST':
        sample_id = request.form.get('sample_id', '').strip().upper()
        update_field = request.form.get('update_field', '').strip()
        update_value = request.form.get('update_value', '').strip()

        def render_error(msg):
            flash(msg, 'error')
            sample_ids = fetch_all("""
                SELECT s.sample_id, p.patient_name
                FROM samples s
                JOIN patients p ON p.patient_id = s.patient_id
                ORDER BY s.sample_id
            """)
            patient_ids = fetch_all("""
                SELECT patient_id, patient_name
                FROM patients
                ORDER BY patient_id
            """)
            return render_template(
                'sample_update.html',
                sample_fields=sample_fields,
                sample_ids=sample_ids,
                patient_ids=patient_ids,
                sample_id=sample_id,
                update_field=update_field,
                update_value=update_value
            )

        if not sample_id or not update_field or not update_value:
            return render_error('Sample ID, update field, and update value are required.')

        if not re.match(r'^S\d{6}$', sample_id):
            return render_error('Sample ID must follow the format S000001, S000002 ... S999999.')

        if update_field not in sample_fields:
            return render_error('Invalid sample field selected.')

        existing_sample = fetch_one('SELECT sample_id FROM samples WHERE sample_id = %s', (sample_id,))
        if not existing_sample:
            return render_error('Sample was not found.')

        if update_field == 'patient_id':
            patient = fetch_one('SELECT patient_id FROM patients WHERE patient_id = %s', (update_value,))
            if not patient:
                return render_error('Selected patient does not exist.')

        if update_field == 'sample_type' and update_value not in ['Blood', 'Swab', 'Tissue']:
            return render_error('Sample type must be Blood, Swab, or Tissue.')

        if update_field == 'collection_date':
            try:
                if date.fromisoformat(update_value) > date.today():
                    return render_error('Collection date cannot be in the future.')
            except ValueError:
                return render_error('Invalid date format. Use YYYY-MM-DD.')

        if update_field in ('referring_doctor', 'referring_hospital', 'test'):
            if not update_value:
                return render_error(f'{sample_fields[update_field]} cannot be empty.')
            
        cur = mysql.connection.cursor()
        cur.execute(
            f"UPDATE samples SET {update_field} = %s WHERE sample_id = %s",
            (update_value, sample_id)
        )
        mysql.connection.commit()
        cur.close()
        flash(f'{sample_fields[update_field]} updated successfully.', 'success')
        return redirect(url_for('sample_update'))

    sample_ids = fetch_all("""
        SELECT s.sample_id, p.patient_name
        FROM samples s
        JOIN patients p ON p.patient_id = s.patient_id
        ORDER BY s.sample_id
    """)
    patient_ids = fetch_all("""
        SELECT patient_id, patient_name
        FROM patients
        ORDER BY patient_id
    """)
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
                patients=patients,
                sample=submitted,
                mode='edit'
            )

        #  1. Required fields 
        if not patient_id or not sample_type or not test or not collection_date or not referring_doctor or not referring_hospital:
            return render_error('All fields are required.')

        #  2. Sample type whitelist 
        if sample_type not in ['Blood', 'Swab', 'Tissue']:
            return render_error('Invalid sample type.')

        #  3. Date not in the future 
        from datetime import date
        try:
            if date.fromisoformat(collection_date) > date.today():
                return render_error('Collection date cannot be in the future.')
        except ValueError:
            return render_error('Invalid date format.')

        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                UPDATE samples
                SET patient_id = %s, sample_type = %s, test = %s,
                    collection_date = %s, referring_doctor = %s, referring_hospital = %s
                WHERE sample_id = %s
            """, (patient_id, sample_type, test, collection_date, referring_doctor, referring_hospital, sample_id))
            mysql.connection.commit()
            flash('Sample updated successfully.', 'success')
            return redirect(url_for('sample_update'))
        except IntegrityError:
            mysql.connection.rollback()
            return render_error('The selected patient is invalid.')
        finally:
            cur.close()
    patients = fetch_all('SELECT patient_id, patient_name FROM patients ORDER BY patient_name')
    return render_template(
            'sample_register.html',
            patients=patients,
            sample=selected_sample, # Passes existing data to populate the form
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

@app.route('/reporting')
@login_required
def reporting():
    return render_template('reporting.html')


if __name__ == '__main__':
    app.run(debug=True)


