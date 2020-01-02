### SSM Parameter Resources ###
resource "aws_ssm_parameter" "shift_login_username" {
  name        = "/${var.ssm_param_path_name}/shift_login/username"
  description = "username for logging into SHiFT account"
  type        = "String"
  value       = var.ssm_param_shift_login_username
}

resource "aws_ssm_parameter" "shift_login_password" {
  name        = "/${var.ssm_param_path_name}/shift_login/password"
  description = "password for logging into SHiFT account"
  type        = "SecureString"
  value       = var.ssm_param_shift_login_password
}

resource "aws_ssm_parameter" "twitter_api_access_token" {
  name  = "/${var.ssm_param_path_name}/twitter/api/access_token"
  type  = "SecureString"
  value = var.ssm_param_twitter_api_access_token
}

resource "aws_ssm_parameter" "twitter_api_access_token_secret" {
  name  = "/${var.ssm_param_path_name}/twitter/api/access_token_secret"
  type  = "SecureString"
  value = var.ssm_param_twitter_api_access_token_secret
}

resource "aws_ssm_parameter" "twitter_api_consumer_key" {
  name  = "/${var.ssm_param_path_name}/twitter/api/consumer_key"
  type  = "SecureString"
  value = var.ssm_param_twitter_api_consumer_key
}

resource "aws_ssm_parameter" "twitter_api_consumer_secret" {
  name  = "/${var.ssm_param_path_name}/twitter/api/consumer_secret"
  type  = "SecureString"
  value = var.ssm_param_twitter_api_consumer_secret
}

### SQS Resources ###

resource "aws_sqs_queue" "redeem_queue_deadletter" {
  name = "${var.sqs_redeem_queue_name}_dlq"
}

resource "aws_sqs_queue" "redeem_queue" {
  name           = var.sqs_redeem_queue_name
  redrive_policy = "{\"deadLetterTargetArn\":\"${aws_sqs_queue.redeem_queue_deadletter.arn}\",\"maxReceiveCount\":3}"
}

resource "aws_sqs_queue" "publish_queue_deadletter" {
  name = "${var.sqs_publish_queue_name}_dlq"
}

resource "aws_sqs_queue" "publish_queue" {
  name           = var.sqs_publish_queue_name
  redrive_policy = "{\"deadLetterTargetArn\":\"${aws_sqs_queue.publish_queue_deadletter.arn}\",\"maxReceiveCount\":3}"
}

### DynamoDB Resources ###

resource "aws_dynamodb_table" "autoshift_table" {
  name           = var.dynamodb_table_name
  hash_key       = "shiftCode"
  range_key      = "tweetTime"
  billing_mode   = "PROVISIONED"
  read_capacity  = 5
  write_capacity = 5

  attribute {
    name = "shiftCode"
    type = "S"
  }

  attribute {
    name = "tweetTime"
    type = "N"
  }
}

### Lambda Function Resources ###

# IAM Roles and Policies
resource "aws_iam_role" "autoshift_lambda_exec_role" {
  assume_role_policy = data.aws_iam_policy_document.autoshift_assume_role_policy.json
  name               = var.lambda_exec_role_name
}

resource "aws_iam_role_policy" "autoshift_lambda_exec_role" {
  name   = var.lambda_exec_role_policy_name
  policy = data.aws_iam_policy_document.autoshift_lambda_exec_role.json
  role   = aws_iam_role.autoshift_lambda_exec_role.id
}

# Fetch Lambda
resource "aws_lambda_function" "autoshift_lambda_fetch" {
  function_name = "${var.lambda_function_name}_fetch"
  handler       = "fetch.handler_fetch"
  role          = aws_iam_role.autoshift_lambda_exec_role.arn
  runtime       = var.python_runtime
  s3_bucket     = var.lambda_deployment_package_s3_bucket
  s3_key        = "${var.lambda_deployment_package_s3_path}/${var.lambda_function_name}.zip"
  timeout       = var.fetch_timeout

  environment {
    variables = {
      SSM_PARAM_PATH_NAME = var.ssm_param_path_name
      PUBLISH_QUEUE_NAME  = var.sqs_publish_queue_name
      REDEEM_QUEUE_NAME   = var.sqs_redeem_queue_name
    }
  }
}

resource "aws_lambda_permission" "cloudwatch_events" {
  statement_id  = "AutoshiftFetchCloudwatchEvent"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.autoshift_lambda_fetch.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.fetch_scheduler.arn
}

resource "aws_cloudwatch_event_rule" "fetch_scheduler" {
  name                = "AutoshiftFetchScheduler"
  schedule_expression = "cron(14 10,13,16,19,22 * * ? *)"
  is_enabled          = true
}

resource "aws_cloudwatch_event_target" "fetch_scheduler" {
  target_id = "AutoshiftFetchLambdaFunction"
  arn       = aws_lambda_function.autoshift_lambda_fetch.arn
  rule      = aws_cloudwatch_event_rule.fetch_scheduler.name
}

# Redeem Lambda
resource "aws_lambda_function" "autoshift_lambda_redeem" {
  function_name = "${var.lambda_function_name}_redeem"
  handler       = "redeem.handler_redeem"
  role          = aws_iam_role.autoshift_lambda_exec_role.arn
  runtime       = var.python_runtime
  s3_bucket     = var.lambda_deployment_package_s3_bucket
  s3_key        = "${var.lambda_deployment_package_s3_path}/${var.lambda_function_name}.zip"
  timeout       = var.redeem_timeout

  environment {
    variables = {
      SSM_PARAM_PATH_NAME = var.ssm_param_path_name
      REDEEM_QUEUE_NAME   = var.sqs_redeem_queue_name
    }
  }
}

resource "aws_lambda_event_source_mapping" "redeem_trigger" {
  event_source_arn = aws_sqs_queue.redeem_queue.arn
  function_name    = aws_lambda_function.autoshift_lambda_redeem.arn
  enabled          = true
  batch_size       = 1
}
/*
not ready yet
# Publish Lambda
resource "aws_lambda_function" "autoshift_lambda_publish" {
  function_name = "${var.lambda_function_name}_publish"
  handler       = "handler"
  role          = aws_iam_role.autoshift_lambda_exec_role.arn
  runtime       = var.python_runtime
  s3_bucket     = var.lambda_deployment_package_s3_bucket
  s3_key        = "${var.lambda_deployment_package_s3_path}/${var.lambda_function_name}.zip"
  timeout       = var.redeem_timeout

  environment {
    variables = {
      SSM_PARAM_PATH_NAME = var.ssm_param_path_name
      PUBLISH_QUEUE_NAME = var.sqs_redeem_queue_name
    }
  }
}

resource "aws_lambda_event_source_mapping" "publish_trigger" {
  event_source_arn = aws_sqs_queue.publish_queue.arn
  function_name = aws_lambda_function.autoshift_lambda_publish.arn
  enabled = true
  batch_size = 1
}
*/