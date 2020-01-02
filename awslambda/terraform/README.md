# AutoSHiFT AWS Lambda Deployment

I'm assuming you're at least familiar with Terraform and will not be breaking down the myriad configuration options for 
a given Terraform project. I will provide examples of the backend and variable files I use to build and deploy, but 
the point here is a quick setup for the resources needed to run Autoshift purely on AWS services.

This Terraform configuration will deploy all of the resources required to run the Lambda version of `autoshift`. It
WILL cost $$MONEY$$ so be aware. That said, it shouldn't cost much more than a dollar or so per month unless you make 
significant changes to the execution schedule or DynamoDB performance configuration.

## Dependencies

* An AWS account with valid SDK/API credentials.
* An active Twitter developer account with valid API credentials.
* [Terraform 0.12.x or newer](https://www.terraform.io/downloads.html)

## Provided AWS Resources That Will Cost You Money

* **Lambda Functions**: 

    `autoshift_fetch`  - Reads Twitter API, checks results against DynamoDB, and puts any new shift codes on queue to
                         be redeemed.

    `autoshift_redeem` - Consumes from redeem queue and attempts to redeem shift codes in your Gearbox account.

* **DynamoDB Tables**: 

    `autoshift` - Permanent record of codes that `autoshift` has redeemed for you. Tracks state of each code as it goes 
                  through the process of being fetched, redeemed, and published/syndicated.

* **SQS Queues**: 

    `autoshift_redeem` - Messages contain SHiFT code data to be redeemed. Message arrival on the queue triggers the 
                         `autoshift_redeem` function.
    
    `autoshift_redeem_dlq` - Dead letter queue for messages that encounter an error during redemption.
    
    `autoshift_publish` - Triggers `autoshift_publish` function.

## Input Variables and Configuration

### Input Variables

Most of the variables have sensible defaults, but you'll need to provide values for the ones that have none. Take a 
look at [vars.tf](./vars.tf) and make sure the defaults will work for you. The only ones that don't have a default are 
items that will be unique to each user, like API keys, bucket names, etc.

I've written the Lambda functions to fetch those secrets from AWS SSM Parameter Store secure strings, and written the 
Terraform configuration to provide them. I suggest using a vars file that is **NOT** checked into VCS (note that 
`*.tfvars` files are in the `.gitignore`).

**Example `tfvars` file**

```hcl
provider_profile                          = "your_aws_profile_name_here"
lambda_deployment_package_s3_bucket       = "s3_bucket_name_where_you_keep_your_lambda_zip"
lambda_deployment_package_s3_path         = "s3/key/path/to/your/lambda.zip"
ssm_param_shift_login_password            = "cleartext-shift.gearbox.com-password"
ssm_param_shift_login_username            = "shift.gearbox.com-username-(usually an email address)"
ssm_param_twitter_api_access_token        = "twitter-developer-account-api-access-token"
ssm_param_twitter_api_access_token_secret = "twitter-developer-account-api-access-token-secret"
ssm_param_twitter_api_consumer_key        = "twitter-developer-account-api-consumer-you-get-the-idea"
ssm_param_twitter_api_consumer_secret     = "twitter-developer-account-api-consumer-you-get-the-idea"
```

**Example `terraform plan` using tfvars file**:

```
terraform plan -var-file=autoshift.tfvars -out /tmp/autoshift.tfplan
```

### Backend Configuration

I also suggest using Terraform remote state if you intend to use this project beyond just an initial plaything, but...
Terraform state still has a big security caveat when it comes to state and secrets.

**BIG SECURITY CAVEAT**: Your clear-text secrets WILL be written to the Terraform state file if you use this. Take the 
appropriate precautions for your chosen backend.

This is the config I use (S3 bucket, values altered for example) as a remote state backend:

```hcl
terraform {
  backend "s3" {
    bucket = "srussell-terraform"
    key    = "lambda/autoshift.tfstate"
    region = "us-west-1"
  }
}
```

## Deployment

Provided you have your Lambda deployment package (zip) in place and have all your configuration items squared, the rest
is just going through the initialization, plan, and apply.

From this directory (`autoshift/awslambda/terraform`), run the following:

```
terraform init
terraform plan -var-file=autoshift.tfvars -out /tmp/autoshift.tfplan
terraform apply /tmp/autoshift.tfplan
```

If you've kept all the defaults, your fetch Lambda will run five times per day between 10:00 AM UTC and 10:00 PM UTC. If
it finds any new SHiFT codes on the `dgSHiFTcodes` Twitter bot stream, it'll write them to DynamoDB, put them on SQS, 
and the redeemer Lambda will attempt to do its thing.
