from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
from dotenv import load_dotenv  # to create a '.env' file and store environment variables
import os

# load the '.env' file and its values, then we access them after importing 'os' module:
load_dotenv()

# define a python 'admin_only' decorator (following the way of '@login_required' decorator function):
def admin_only(function):

    @wraps(function)   # as per doc
    # define the wrapper function (function to do sth before or after or test sth for the 'function') takes parameters tuple 'args' and
    # dict 'kwargs' cz 'function' has parameter (ex: edit_post(post_id) this function takes a positional arg post_id):
    def wrapper_function(*args, **kwargs):
        # If id is not 1 (not admin) then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        # Otherwise continue with the route function
        return function(*args, **kwargs)

    # finally return the wrapper function:
    return wrapper_function

# after defining the above decorator, we need to mark every route we want to protect (admin only) with '@admin_only' decorator

app = Flask(__name__)
# configure the flask app secret key from the saved external environment variable using getenv() method from os module:
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)

# Initialize gravatar extention with flask application as per doc (we can only put 'gravatar = Gravatar(app)' also):
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


##CONNECT TO DB
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
# instead of connecting to sqlite db like above we shld connect to Postgres db from Heroku, using config var file (like .env) name of database
# variable is 'DATABASE_URL', so we use 'os.getenv()' method as if its a '.env' file:
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", default="sqlite:///blog.db")   # add a default value for local deployment
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configure authentication with Flask-login:
login_manager = LoginManager(app)
# create a user_loader function to reload the user object from the user ID stored in the session:
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


##CONFIGURE TABLES

# define Users table in database (database can have several tables inside) and add 'UserMixin' for authentication uses (inheriting attributes):
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)     # 500 characters cz password hash might be long
    name = db.Column(db.String(100), nullable=False)

    # Create the relationship with child class 'BlogPost'. This will act like a List of 'BlogPost' objects attached to each
    # 'User'. The "author" refers to the author property in the BlogPost class:
    blogposts = relationship('BlogPost', back_populates='author')
    # Create the relationship with child class 'Comment'. This will act like a List of 'Comment' objects attached to each
    # 'User'. The "comment_author" refers to the comment_author property in the Comment class:
    comments = relationship('Comment', back_populates='comment_author')

class BlogPost(db.Model):
    # define a name to this created table using '__tablename__' attribute:
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    # Create Foreign Key to reference the relationship, "users.id" the 'users' refers to the tablename of 'User' class (parent table):
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # Create reference to the User object, the "blogposts" refers to the blogposts property in the 'User' class.
    author = relationship('User', back_populates='blogposts')

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # Create the relationship with child class 'Comment'. This will act like a List of 'Comment' objects attached to each
    # 'BlogPost'. The "parent_post" refers to the parent_post property in the Comment class:
    comments = relationship('Comment', back_populates='parent_post')

# create comments table in relationship with User table so users can leave comments and save them:
class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    # Create Foreign Key to reference the relationship, "users.id" the 'users' refers to the tablename of 'User' class (parent table):
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # Create reference to the User object, the "comments" refers to the comments property in the 'User' class.
    comment_author = relationship("User", back_populates='comments')

    # Create Foreign Key to reference the relationship, "blog_posts.id" 'blog_posts' refers to the tablename of 'BlogPost' class (parent table):
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    # Create reference to the BlogPost object, the "comments" refers to the comments property in the 'BlogPost' class.
    parent_post = relationship("BlogPost", back_populates='comments')



db.create_all()

# No need to pass the 'current_user' over to the template everytime we call render_template(), we can directly check if
# 'current_user.is_authenticated' is True in any template, since Flask-login uses session and in every session login_manager loads user from
# id (string) and return user object that can be accessed with 'current_user' (user object)

@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["GET", "POST"])
def register():
    # create the registering form:
    register_form = RegisterForm ()

    if register_form.validate_on_submit():
        # get the email entered in form and tap into the related user from db:
        email_entered = register_form.email.data
        user = User.query.filter_by(email=email_entered).first()

        # if user exists in db flash a warning and redirect him to 'login.html':
        if user:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))
        # if user does not exist in db register him:
        else:
            # create a new record (user) from data inserted in form using 'form.field.data' method and not 'request.form.get()' since its wtf
            # form and not html form (also hash and salt the password before adding it to the record to be saved in db):
            new_user = User(
                email=email_entered,
                password=generate_password_hash(password=register_form.password.data,method='pbkdf2:sha256',salt_length=8),
                name=register_form.name.data
            )
            # add this new record to database:
            db.session.add(new_user)
            db.session.commit()
            # login new user (authenticate them with Flask-Login) and redirect them to home page after saving db:
            login_user(new_user)
            return redirect(url_for('get_all_posts'))

    # if its a "GET" method requested go to 'register.html' with the registering form passed as variable:
    return render_template("register.html", form=register_form)


@app.route('/login', methods=["GET", "POST"])
def login():
    # create the registering form:
    login_form = LoginForm()

    if login_form.validate_on_submit():
        # if form is submitted which means 'POST' method, assign the form data entered:
        email_entered = login_form.email.data
        password_entered = login_form.password.data
        # get the user from db using the email entered:
        user = User.query.filter_by(email=email_entered).first()
        # if user not available flash a warning:
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        # if wrong password flash a warning:
        elif not check_password_hash(pwhash=user.password,password=password_entered):
            flash("Password incorrect, please try again.")
            return redirect(url_for('login'))
        # if user exists and correct password login user and go to homepage:
        else:
            login_user(user)
            return redirect(url_for('get_all_posts'))

    # if its a "GET" method requested go to 'login.html' with the login form passed as variable:
    return render_template("login.html", form=login_form)


@app.route('/logout')
@login_required         # secure this route so that only authenticated users can access it
def logout():
    # log user out:
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    # define the comment form and pass it as variable to 'post.html':
    comment_form = CommentForm()

    # form is submitted and method is post
    if comment_form.validate_on_submit():
        # if user isnt logged in flash him a warning and take him to 'login' route:
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for('login'))

        # otherwise (logged in) create a new comment record from data inserted in form and save it to database:
        new_comment = Comment(text=comment_form.comment.data, comment_author=current_user, parent_post=requested_post)
        db.session.add(new_comment)
        db.session.commit()
        # empty the ckeditor box (to not stay in the editor) so going down in code it will go to this same route but with empty comment editor:
        comment_form.comment.data = ""

    # if method is "GET" pass 'post' and 'form' variables and redirect to 'post.html', also after saving the comment in db (but in this case the
    # form comment_text is empty) :
    return render_template("post.html", post=requested_post, form=comment_form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_only         # secure this route so that only authenticated users can access it
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,            # html.unescape(form.body.data),
            img_url=form.img_url.data,
            author=current_user,    # the author is an object not a name
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only         # secure this route so that only authenticated users can access it
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        # author=post.author,       # remove this line cz in this project no author attribute for 'createPostForm' class
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        # post.author = edit_form.author.data       # remove this line cz in this project no author attribute for 'createPostForm' class
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only         # secure this route so that only authenticated users can access it
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))

# create a delete comment route for users:
@app.route("/delete-comment/<int:comment_id>")
@login_required     # secure this route so that only authenticated users can access it
def delete_comment(comment_id):
    # get the comment from db using its id:
    comment_to_delete = Comment.query.get(comment_id)
    # delete this comment from db:
    db.session.delete(comment_to_delete)
    db.session.commit()
    # redirect to 'show_post' route and pass the variable 'post_id' of the comment's parent post using the relationship:
    return redirect(url_for('show_post', post_id=comment_to_delete.post_id))

if __name__ == "__main__":
    # app.run(host='0.0.0.0', port=5000)
    app.run(debug=True)   # Removing the above params will let it run on our machine


