#!/usr/bin/env bash

ADDON_NAME=$(ls $INPUT_APP_PATH)
ADDON_FULL_PATH="$INPUT_APP_PATH/$ADDON_NAME"

echo "username = $INPUT_USERNAME"
echo "i tags = $INPUT_INCLUDED_TAGS"

python3 /main.py $INPUT_USERNAME $INPUT_PASSWORD $ADDON_FULL_PATH $INPUT_INCLUDED_TAGS $INPUT_EXCLUDED_TAGS
