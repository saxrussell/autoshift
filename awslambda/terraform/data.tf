provider "aws" {
  profile = var.provider_profile
  region  = var.provider_region
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "autoshift_assume_role_policy" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      identifiers = [
        "lambda.amazonaws.com"
      ]
      type = "Service"
    }
  }
}

data "aws_iam_policy_document" "autoshift_lambda_exec_role" {
  statement {
    sid    = "AutoshiftLambdaKmsAccess"
    effect = "Allow"
    actions = [
      "kms:Get*",
      "kms:List*",
      "kms:Decrypt"
    ]
    resources = ["*"]
  }

  statement {
    sid    = "AutoshiftParamStoreAccess"
    effect = "Allow"
    actions = [
      "ssm:Describe*",
      "ssm:Get*"
    ]
    resources = [
      "*"
    ]
  }

  statement {
    sid    = "AutoshiftLambdaDynamoAccess"
    effect = "Allow"
    actions = [
      "dynamodb:BatchGet*",
      "dynamodb:Describe*",
      "dynamodb:Get*",
      "dynamodb:DeleteItem",
      "dynamodb:List*",
      "dynamodb:Query",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
      "dynamodb:UpdateItem",
      "dynamodb:Scan"
    ]
    resources = ["*"]
  }

  statement {
    sid    = "AutoshiftLambdaSqsAccess"
    effect = "Allow"
    actions = [
      "sqs:Get*",
      "sqs:List*",
      "sqs:SendMessage*",
      "sqs:ReceiveMessage*",
      "sqs:DeleteMessage*"
    ]
    resources = ["*"]
  }

  statement {
    sid    = "AutoshiftLambdaS3Access"
    effect = "Allow"
    actions = [
      "s3:List*",
      "s3:Get*",
    ]
    resources = [
      "arn:aws:s3:::${var.lambda_deployment_package_s3_bucket}",
      "arn:aws:s3:::${var.lambda_deployment_package_s3_bucket}/*"
    ]
  }

  statement {
    sid    = "AutoshiftLambdaCloudwatchLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = [
      "arn:aws:logs:*:*:*"
    ]
  }
}