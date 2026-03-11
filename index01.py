import jwt
import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, make_response, url_for
from models import db, User, StudentProfile, CompanyProfile, PlacementDrive, Application
from werkzeug.security import generate_password_hash, check_password_hash