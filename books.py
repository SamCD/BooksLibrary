import sqlite3,json, urllib2
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash
from contextlib import closing

api_str = 'https://www.googleapis.com/books/v1/volumes?q=isbn:'

DATABASE = 'books.db'
DEBUG = True
SECRET_KEY = '7\xb4\xc0\x1f\x97\xbe\xbc\xa3\xe0\xe6'
USERNAME = 'admin'
PASSWORD = 'password'

app = Flask(__name__)
app.config.from_object(__name__)

def connect_db():
    return sqlite3.connect(app.config['DATABASE'])

def init_db():
    with closing(connect_db()) as db:
        with app.open_resource('books.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

connect_db()
init_db()

@app.before_request
def before_request():
    g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()
        
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    error = None
    if request.method == 'POST':
        cur1 = g.db.execute('select uname,pword from Users where uname=?',
                            [request.form['username']])
        users = cur1.fetchall()
        if not users:
            error="Invalid username"
        elif request.form['password'] != users[0][1]:
            error="Invalid password"
        else:
            session['username'] = request.form['username']
            session['logged_in'] = True
            flash('Logged in as {}'.format(session['username']))
            return redirect(url_for('show_books'))
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You were logged out')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        cur1 = g.db.execute('select uname from Users')
        dblist = [row[0] for row in cur1.fetchall()]
        if request.form['username'] in dblist:
            flash('Username already exists')
            return redirect(url_for('login'))
        g.db.execute('insert into Users (uname,pword) values (?,?)',
                     [request.form['username'],
                      request.form['password']])
        g.db.commit()
        flash('New user created')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
def show_books():
    cur1 = g.db.execute('select ISBN, Title, Author, Pages, '\
                        'avgReview,Thumb,userID from Books b '\
                        'inner join Users u on b.userID = u.ID '\
                        'where u.uname=?',[session['username'].decode()])
    books = [dict(isbn=row[0]
                  ,title=row[1]
                  ,author=row[2]
                  ,pages=row[3]
                  ,rev=row[4]
                  ,thumb=row[5]) for row in cur1.fetchall()]
    return render_template('show_books.html'
                           , books=books)

@app.route('/book/add', methods=['GET','POST'])
def add_book():
    if request.method == 'POST':
        if not session.get('logged_in'):
            abort(401)
        response = urllib2.urlopen(api_str + request.form['isbn'])
        data = json.loads(response.read())
        success = False
        try:
            g.db.execute('insert into Books (ISBN,Title,Author,Pages,'\
                         'avgReview,Thumb,userID) '\
                     'values (?,?,?,?,?,?,(select ID from Users where uname=?))',
                     [request.form['isbn']
                      , data['items'][0]['volumeInfo']['title'].decode()
                      , data['items'][0]['volumeInfo']['authors'][0].decode()
                      , data['items'][0]['volumeInfo']['pageCount']
                      , data['items'][0]['volumeInfo']['averageRating']
                      ,data['items'][0]['volumeInfo']\
                      ['imageLinks']['smallThumbnail']
                      , session['username']
                      ]
                         )
            g.db.commit()
            success = True
        except KeyError:
            flash('Please enter a valid ISBN')
            return redirect(url_for('add_book'))
        if success:    
            flash('{} by {} was successfully added'.format(
                        data['items'][0]['volumeInfo']['title'].decode()
                        , data['items'][0]['volumeInfo']['authors'][0].decode()
                        )
                  )
        return redirect(url_for('show_books'))
    return render_template('add_book.html')

@app.route('/book/delete/<isbn>', methods=['GET','POST'])
def delete_book(isbn):
    if request.method == 'POST':
        if not session.get('logged_in'):
            abort(401)
        g.db.execute('delete from Books where ISBN = ?'
                    ,[isbn])
        g.db.commit()
    return redirect(url_for('show_books'))

if __name__ == '__main__':
    app.run()
