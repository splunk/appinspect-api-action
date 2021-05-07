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

| Name             | Description                                                                                                       |
| ---------------- | ----------------------------------------------------------------------------------------------------------------- |
| `filePath`       | Path to the app bundle file (.tar.gz or .spl)                                                                     |
| `splunkUser`     | Splunk.com user used to login to the appinspect API                                                               |
| `splunkPassword` | Splunk.com password used to login to the appinspect API                                                           |
| `includedTags`   | Optional: Comma separated list of [tags](#tags) to include in appinspect job                                      |
| `excludedTags`   | Optional: Comma separated list of [tags](#tags) to exclude from appinspect job                                    |
| `failOnError`    | Optional: If enabled the action will fail when errors or failures are reported by AppInspect (enabled by default) |
| `failOnWarning`  | Optional: If enabled the action will fail when warnings are reported by AppInspect                                |

### Tags

For more info on tags see [Splunk AppInspect tag reference](https://dev.splunk.com/enterprise/docs/reference/appinspecttagreference).
