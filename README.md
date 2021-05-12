# App Inspect API GitHub Action

Simple GitHub action to validation a Splunk app package using AppInspect. This action uses the [Splunkbase AppInspect API](https://dev.splunk.com/enterprise/docs/developapps/testvalidate/appinspect/runappinspectrequestsapi).

There is also an [alternative GitHub action using the AppInspect CLI](https://github.com/splunk/appinspect-cli-action).

## Example Usage

```yaml
jobs:
    some-job:
        runs-on: ubuntu-latest
        steps:
            # ...
            - uses: splunk/appinspect-api-action@v2
              with:
                  filePath: ./dist/myapp.tar.gz
                  splunkUser: ${{ secrets.SPLUNKBASE_USER }}
                  splunkPassword: ${{ secrets.SPLUNKBASE_PASSWORD }}
                  includedTags: cloud
                  failOnError: true
                  failOnWarning: true
```

## Inputs

| Name                   | Description                                                                                                | Notes            |
| ---------------------- | ---------------------------------------------------------------------------------------------------------- | ---------------- |
| `filePath`             | Path to the app bundle file (.tar.gz or .spl)                                                              | **required**     |
| `splunkUser`           | Splunk.com user used to login to the appinspect API                                                        | **required**     |
| `splunkPassword`       | Splunk.com password used to login to the appinspect API                                                    | **required**     |
| `includedTags`         | Comma separated list of [tags](#reference-docs) to include in appinspect job                               |                  |
| `excludedTags`         | Comma separated list of [tags](#reference-docs) to exclude from appinspect job                             |                  |
| `failOnError`          | If enabled the action will fail when errors or failures are reported by AppInspect                         | default: `true`  |
| `failOnWarning`        | If enabled the action will fail when warnings are reported by AppInspect                                   | default: `false` |
| `ignoredChecks`        | Comma separated list of [check names](#reference-docs) to explicitly ignore                                |                  |
| `uploadReportArtifact` | If enabled the action will upload the HTML report from the AppInspect API as an artifact to GitHub actions | default: `true`  |

### Reference Docs

For more info on check critera, tags and the API see the [Splunk AppInspect reference](https://dev.splunk.com/enterprise/reference/appinspect).
