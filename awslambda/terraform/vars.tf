variable "lambda_deployment_package_s3_bucket" {}
variable "lambda_deployment_package_s3_path" {}
variable "ssm_param_shift_login_password" {}
variable "ssm_param_shift_login_username" {}
variable "ssm_param_twitter_api_access_token" {}
variable "ssm_param_twitter_api_access_token_secret" {}
variable "ssm_param_twitter_api_consumer_key" {}
variable "ssm_param_twitter_api_consumer_secret" {}

variable "provider_profile" {
  type = string

  default = "default"
}

variable "provider_region" {
  type = string

  default = "us-west-2"
}

variable "ssm_param_path_name" {
  type = string

  default = "autoshift"
}

variable "sqs_redeem_queue_name" {
  type = string

  default = "shift_code_redeem"
}

variable "sqs_publish_queue_name" {
  type = string

  default = "shift_code_publish"
}

variable "dynamodb_table_name" {
  type = string

  default = "autoshift"
}

variable "lambda_exec_role_name" {
  type = string

  default = "autoshift_lambda"
}

variable "lambda_exec_role_policy_name" {
  type = string

  default = "autoshift_lambda"
}

variable "lambda_function_name" {
  type = string

  default = "autoshift"
}

variable "lambda_log_level" {
  type = string

  default = "INFO"
}

variable "lambda_log_retention" {
  type        = number
  description = "number of days to retain lambda execution logs in cloudwatch"

  default = 14
}

variable "publish_lambda_function_name" {
  type = string

  default = "autoshift_publish"
}

variable "redeem_timeout" {
  type = string

  default = "10"
}

variable "fetch_timeout" {
  type = string

  default = "10"
}

variable "publish_timeout" {
  type = string

  default = "10"
}

variable "python_runtime" {
  type = string

  default = "python3.7"
}