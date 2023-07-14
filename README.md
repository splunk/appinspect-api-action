# Simple App Inspect API GitHub Action

Simple GitHub action to validation a Splunk app package using AppInspect API. This action uses the [Splunkbase AppInspect API](https://dev.splunk.com/enterprise/docs/developapps/testvalidate/appinspect/runappinspectrequestsapi).

There is also an [GitHub action using the AppInspect CLI](https://github.com/splunk/appinspect-cli-action).

## Example Usage

```yaml
jobs:
  appinspect-job:
    runs-on: ubuntu-latest
    steps:
      # ...
      - uses: splunk/appinspect-api-action@v3
        with:
          username: ${{ secrets.SPL_COM_USER }}
          password: ${{ secrets.SPL_COM_PASSWORD }}
          app_path: build/package/
          included_tags: "cloud,self-service"
          excluded_tags: "offensive"
```

## Inputs

| Name            | Description                                                                    | Notes        | Default |
|-----------------|--------------------------------------------------------------------------------|--------------|---------|
| `username`      | Splunk.com user used to login to the appinspect API                            | **required** |         |
| `password`      | Splunk.com password used to login to the appinspect API                        | **required** |         |
| `app_path`      | Path to the directory where addon is located, without filename                 | **required** |         |
| `included_tags` | Comma separated list of [tags](#reference-docs) to include in appinspect job   |              | None    |
| `excluded_tags` | Comma separated list of [tags](#reference-docs) to exclude from appinspect job |              | None    |

You can explicitly include and exclude tags from a validation by including additional options in your request. Specifically, using the included_tags and excluded_tags options includes and excludes the tags you specify from a validation. If no tags are specified all checks will be done and no tags are excluded from the validation.

Appinspect failures are handled via `.appinspect_api.expect.yaml` file. To make exceptions the file should look like that:

```yaml
name_of_the_failed_checks:
  comment: jira-123
```

If you are a Splunker please specify jira issue in the comment where reason for exception is granted and explained

### Reference Docs

For more info on check criteria, tags and the API see the [Splunk AppInspect reference](https://dev.splunk.com/enterprise/reference/appinspect).


### Differences between v2 

Missing parameters:
    
- `failOnError` - hardcoded to be true
- `failOnWarning` - hardcoded to be false
- `ignoredChecks` - hardcoded to be None
- `uploadReportArtifact` - by default html report will be generated as AppInspect_response.html, to upload it please use upload-artifact-v3
