import os
import logging
import boto3
import tarfile
import zipfile
import glob
import logging
import uuid
import shutil
from pathlib import Path
from enum import Enum
from botocore.exceptions import ClientError

class Task(Enum):
	oneA = '1a'
	oneB = '1b'
	two = '2'
	three = '3'

# define all the different directory types and corresponding flags
NIST = { 'validation': '--ldc --nist -o', 'name': 'nist', 'directory': 'NIST'  }
INTER_TA = { 'validation': '--ldc -o', 'name': 'unrestricted', 'directory': 'INTER-TA'  }
NIST_TA3 = { 'validation': '--ldc --nist-ta3 -o', 'name': 'nist-ta3', 'directory': 'NIST'  }


def download_and_extract_submission_from_s3(session, submission):
	"""Downloads submission from s3 and extracts contents to the working directory.
	Submissions must be an archive of .zip, .tar.gz, or .tgz.

	:param Session session: The boto3 session 
	:param str submission: The path of the submission on s3
	:raises ClientError: SQS client exception
	:raises Exception: No turtle (TTL) files extracted from s3 submission
	:returns: The directory of the extracted content
	:rtype: str
	"""
	s3_bucket, s3_object, file_name, file_ext = get_submission_paths(submission)

	uid = str(uuid.uuid4())

	# create directory for output
	if not os.path.exists(uid):
	    os.makedirs(uid)

	s3_client = session.client('s3')

	try:
	    logging.info("Downloading %s from bucket %s", s3_object, s3_bucket)
	    s3_client.download_file(s3_bucket, s3_object, file_name)
	    logging.info("Extracting %s", file_name)

	    # extract files
	    if file_ext == '.tgz' or file_ext == '.tar.gz':
	        # extract the contents of the .tar.gz
	        with tarfile.open(file_name) as tar:
	            tar.extractall(uid)
	    elif(file_ext == '.zip'):
	        zip_ref = zipfile.ZipFile(file_name, 'r')
	        zip_ref.extractall(uid)
	        zip_ref.close()

	    ttls_paths = (glob.glob(uid + '/**/*.ttl', recursive=True))
	    ttls = [ Path(x).name for x in ttls_paths ]

	    # if no ttl files extracted raise an exception
	    if len(ttls) <= 0 :
	        err = "No files with .ttl extension found in S3 submission {0}".format(file_name)
	        raise ValueError(err)

	    return uid

	except ClientError as e:
	    logging.error(e)
	    raise
	except ValueError as e:
	    logging.error(e)
	    raise


def upload_file_to_s3(session, filepath, bucket, prefix=None):
    """Helper function to upload single file to S3 bucket with specified prefix

    :param str filepath: The local path of the file to be uploaded
    :param str bucket: The S3 bucket to upload file to
    :param str prefix: The prefix to be added to the file name
    :raises ClientError: S3 client exception
    """
    s3_client = session.client('s3')

    try:
        if prefix is not None:
            s3_object = '/'.join([prefix, Path(filepath).name])
        else:
            s3_object = Path(filepath).name

        logging.info("Uploading %s to bucket %s with prefix", s3_object, bucket)
        s3_client.upload_file(str(filepath), bucket, s3_object)

    except ClientError as e:
        logging.error(e)


def get_submission_paths(submission):
    """Helper function to extract s3 and file path information from s3 submission 
    path.

    :returns: 
        - s3_bucket - the extracted S3 bucket
        - s3_object - the extracted s3 object
        - file_name - the extracted file name including extension
        - file_ext - the extracted file extension
    :rtype: (str, str, str, str)
    """
    path = Path(submission)
    s3_bucket = path.parts[0]          
    s3_object = '/'.join(path.parts[1:])   
    file_name = path.name
    suffixes = path.suffixes
    file_ext = get_submission_extension(submission)

    return s3_bucket, s3_object, file_name, file_ext


def get_submission_extension(submission):
	"""Helper function to get the extension of the submission

	:param str submission: The full path of the submission on s3
	:returns: The submission extension
	:rtype: str
	"""
	path = Path(submission)
	suffixes = path.suffixes

	if len(suffixes) > 1 and suffixes[-1] == '.gz':
	    file_ext = "".join([suffixes[-2], suffixes[-1]])
	elif len(suffixes) > 1:
	    file_ext = suffixes[-1]
	elif len(suffixes) == 1:
	    file_ext = suffixes[0]

	return file_ext


def check_submission_extension(submission):
    """Helper function that checks the submission extension is valid before
    downloading archive from S3. Valid submissions can be archived as .tar.gz, 
    .tgz, or .zip. 

	:param str submission: The path of the submission
	:raises ValueError: The submission extension type is invalid
    """
    file_ext = get_submission_extension(submission)
    valid_ext = [".tar.gz", ".tgz", ".zip"]

    try:
        logging.info("Checking if submission %s is a valid archive type", submission)
        if file_ext not in valid_ext:
            raise ValueError("Submission {0} is not a valid archive type".format(submission))
    except ValueError as e:
        logging.error(e)
        raise


def get_submission_stem(submission):
	"""Function will return the stem of the submission accounting for the
	extension .tar.gz.

	:param str submission: The path of the submission on s3
	:returns: The stem of the submission
	:rtype: str
	"""
	path = Path(submission)
	stem = path.stem

	if get_submission_extension(submission) == '.tar.gz':
		return Path(stem).stem
	else:
		return stem


def get_task_type(stem, directory):
	"""Function will determine the task type of the submission based on the naming 
	convention of the stem.

	:param str stem: The stem of the submission
	:param str directory: The local directory containing the donwloaded contents of
		the submission
	:returns The task type enum of the submission stems
	:rtype: Enum
	"""
	delim_count = stem.count('.')

	if delim_count == 0:
		if check_nist_directory(directory) and check_inter_ta_directory(directory):
			return Task.oneA
		elif check_nist(directory):
			return Task.oneB
		else:
			raise ValueError("Invalid Task 1 submission format. Could not locate required %s directory in submission", 
				NIST['directory']) 
	elif delim_count == 1:
		if check_nist_directory(directory):
			return Task.two
		else:
			raise ValueError("Invalid Task 2 submission format. Could not locate required %s directory in submission", 
				NIST['directory']) 
	elif delim_count == 2:
		return Task.three
	else:
		raise ValueError("Invalid submission format. Could not extract task type with submission stem %s", stem) 


def validate_and_upload(session, directory, task, bucket, prefix):
	"""Validates directory structure of task type and then uploads contents to s3. Will return a dictionary
	of the jobs that need to be executed on batch with their corresponding s3 locations.

	:param Session session: The boto3 session
	:param str directory: The local directory containing the donwloaded contents of
		the submission
	:param Task task: The task enum that representing the task type of the submission
	:param str bucket: The S3 bucket
	:param str prefix: The prefix to append to all objects uploaded to the S3 bucket
	:returns: List of dictionary objects representing the aws batch jobs that need to be executed
	:rtype: List
	"""
	logging.info("Validating submission as task type %s", task.value)
	task_type = task.value
	jobs = []

	if task == Task.oneA or task == Task.oneB or task == Task.two:

		# NIST direcotry required, do not upload INTER-TA if NIST does not exist
		if not check_nist_directory(directory):
			logging.error("Task 1 submission format is invalid. Could not locate NIST directory")
		else:
			jobs.append(upload_formatted_submission(session, directory, bucket, prefix, NIST))

			# INTER-TA directory **not required**
			if check_inter_ta_directory(directory):
				jobs.append(upload_formatted_submission(session, directory, bucket, prefix, INTER_TA))

		return jobs

	elif task == Task.three:
		jobs.append(upload_formatted_submission(session, directory, bucket, prefix, NIST_TA3))

	else:
		logging.error("Could not validate submission structure for invalid task %s", task)


def upload_formatted_submission(session, directory, bucket, prefix, validation_type):
	"""Function will locate all ttl files within a submission subdirectory based on the validation 
	type that was found in the get_task_type function and upload them to s3. Once all the files have been 
	uploaded a dictionary object with information to pass into the aws batch job will be returned. 

	:param Session session: The boto3 session
	:param str directory: The local directory containing the donwloaded contents of
		the submission
	:param str bucket: The S3 bucket
	:param str prefix: The prefix to append to all objects uploaded to the S3 bucket
	:param validation_type: The validation type that these files will be validatated against
	:param validation_flags: The validation flags to pass to the AIF validator when validating these
		files. 
	"""
	job = {}
	bucket_prefix = prefix + '-' + validation_type['name']
	logging.info("Task 1 submission %s directory exists. Uploading .ttl files to %s", 
		validation_type, bucket + '/' + bucket_prefix)

	ttl_paths = (glob.glob(directory + '/' + validation_type ['directory'] + '/*.ttl', recursive=True))
	ttls = [ Path(x).name for x in ttl_paths ]

	if not check_for_duplicates(ttls):

		if len(ttls) == 0:
			logging.error("No .ttl files found in Task 1 submission %s directory", validation_type['directory'])
		else:
			for path in ttl_paths:
				upload_file_to_s3(session, path, bucket, bucket_prefix)

			# create the batch job information
			job['s3_submission_bucket'] = bucket
			job['s3_submission_prefix'] = bucket_prefix
			job['validation_flags'] = validation_type['validation']
			job['count'] = len(ttls)

	return job

def check_for_duplicates(ttls):
	"""Function will check to see if there are any duplicates in a list of file names

	:param List ttls: A list of ttl file names.
	:returns: True if duplicates were found, False otherwise
	:rtype: bool
	"""
	if len(ttls) != len(set(ttls)):
		logging.error("Duplicate files with .ttl extension found in submission")
		return True
	return False
		

def check_nist_directory(directory):
	"""Helper function that will determine if NIST directory exists as an 
	immediate subdirectory of the passed in directory.

	:param str directory: The directory to validate against
	:returns: True if directory exists, False otherwise
	:rtype: bool
	"""
	return os.path.exists(directory + "/" + NIST['directory'])


def check_inter_ta_directory(directory):
	"""Helper function that will determine if INTER-TA directory exists as
	an immediate subdirectory of the passed in directory.

	:param str directory: The directory to validate against
	:returns: True if directory exists, False otherwise
	:rtype: bool
	"""
	return os.path.exists(directory + "/" + INTER_TA['directory'])

def main():

	# variables 
	aws_region = 'us-east-1'
	aws_validation_bucket = 'aida-validation'
	submission = 'aida-validation/archives/NextCentury_1.zip'

	# set logging to info
	logging.basicConfig(level=os.environ.get('LOGLEVEL', 'INFO'))
	session = boto3.session.Session(region_name=aws_region)

	check_submission_extension(submission)
	stem = get_submission_stem(submission)
	logging.info("File stem for submission %s is %s", submission, stem)

	staging_dir = download_and_extract_submission_from_s3(session, submission)

	task = get_task_type(stem, staging_dir)

	# validate structure of submission and upload to S3 
	jobs = validate_and_upload(session, staging_dir, task, aws_validation_bucket, stem)

	if len(jobs) > 0:
		logging.info("Submit the following jobs to AWS Batch:")

		for idx, job in enumerate(jobs):
			job['s3_submission_archive'] = Path(submission).name
			job['s3_submission_task'] = task.value
			logging.info("Job %s: %s", str(idx), str(job))

	# remove staing directory and downloaded submission
	os.remove(Path(submission).name)

	logging.info("Removing %s", staging_dir)
	shutil.rmtree(staging_dir)


if __name__ == "__main__": main()
