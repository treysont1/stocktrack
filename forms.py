from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, EmailField
from wtforms.validators import DataRequired, Email, ValidationError

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired()])
    submit = SubmitField('Register')

    # def validate_username(self, username):
    #     username = db.session.scalar(db.select(User).where(User.username == username.data))
    #     if username:
    #         raise ValidationError('Username Taken')
    
    # def validate_email(self, email):
    #     email = db.session.scalar(db.select(User).where(User.email == email.data))
    #     if email:
    #         raise ValidationError('Email Already In Use')
class DeleteAccount(FlaskForm):
    password = PasswordField('Enter password')
    confirm  = SubmitField('Confirm Account Deletion')