import { debug, error, getInput, info, isDebug, setFailed, warning } from '@actions/core';
import { create as createArtifactClient } from '@actions/artifact';
import * as fs from 'fs';
import { Check, getHtmlReport, getReport, getStatus, login, Message, submit, SubmitResponse } from './api';
import { parseBoolean } from './util';

const sleep = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms));

export function formatMessage(message: Message, check: Check): string {
    const lines = [
        message.message,
        '',
        `Check ${check.name}: ${check.description}`,
        `Tags: ${check.tags.join(', ')}`,
        `Filename: ${message.message_filename}${
            message.message_line != null ? ` on line ${message.message_line}` : ''
        }`,
        '',
    ];
    return lines.join('\n');
}

async function appInspect({
    user,
    password,
    filePath,
    includedTags,
    excludedTags,
    failOnError,
    failOnWarning,
    ignoreChecks = [],
    uploadReportArtifact = true,
}: {
    filePath: string;
    user: string;
    password: string;
    includedTags?: string[];
    excludedTags?: string[];
    failOnError: boolean;
    failOnWarning: boolean;
    ignoreChecks?: string[];
    uploadReportArtifact?: boolean;
}): Promise<void> {
    info(`Submitting file ${filePath} to appinspect API...`);
    if (!fs.existsSync(filePath)) {
        throw new Error(`File ${filePath} does not exist`);
    }
    const token = await login(user, password);

    const submitRes: SubmitResponse = await submit({
        filePath,
        token,
        includedTags,
        excludedTags,
    });

    const reqId = submitRes.request_id;
    info(`Submitted and received reqId=${reqId}`);
    info('Waiting for appinspect job to complete...');
    while (true) {
        await sleep(10_000);
        const status = await getStatus({ request_id: reqId, token });
        debug(`Got status ${status.status}`);
        if (status.status === 'SUCCESS') {
            break;
        } else if (status.status === 'PROCESSING') {
            debug('Appinspect job is still processing');
        } else {
            throw new Error(`Unexpected status ${status.status}`);
        }
    }

    info(`Retrieving report for reqId=${reqId}`);
    const reportDoc = await getReport({ request_id: reqId, token });
    if (reportDoc.reports.length !== 1) {
        warning(`Received ${reportDoc.reports.length} report documents. Expected 1.`);
    }
    const report = reportDoc.reports[0];

    info(`Received report for app: ${report.app_name} ${report.app_version} [${report.app_hash}]`);
    info(
        `Tags: ${report.run_parameters.included_tags.join(',')} - excluded: ${report.run_parameters.excluded_tags.join(
            ','
        )}`
    );

    if (uploadReportArtifact) {
        const file = `appinspect_report.html`;
        const htmlContents: string = await getHtmlReport({ request_id: reqId, token });
        fs.writeFileSync(file, htmlContents, { encoding: 'utf-8' });
        await createArtifactClient().uploadArtifact('appinspect_report', [file], process.cwd(), {
            continueOnError: true,
        });
    }

    let errorCount = 0;
    let warningCount = 0;

    const checkMessages = (check: Check): string[] =>
        check.messages == null || check.messages.length === 0
            ? ['No check message']
            : check.messages.map((msg) => formatMessage(msg, check));

    for (const group of report.groups) {
        for (const check of group.checks) {
            if (isDebug()) {
                debug(`Raw check info:\n${JSON.stringify(check, null, 2)}`);
            }
            if (ignoreChecks.includes(check.name) && ['error', 'failure', 'warning'].includes(check.result)) {
                info(`Ignoring check ${check.name} as per configuration.`);
                continue;
            }

            switch (check.result) {
                case 'error':
                case 'failure':
                    for (const msg of checkMessages(check)) {
                        error(msg);
                        errorCount++;
                    }
                    break;
                case 'warning':
                    for (const msg of checkMessages(check)) {
                        warning(msg);
                        warningCount++;
                    }
                    break;
                case 'manual_check':
                    for (const msg of checkMessages(check)) {
                        info(`A manual check is required:\n${msg}`);
                    }
                    break;
                case 'success':
                case 'not_applicable':
                    // ignore
                    break;
                default:
                    throw new Error(`Unexpected check result: ${check.result}`);
            }
        }
    }

    info(`Summary: ${JSON.stringify(report.summary, null, 2)}`);

    if (report.summary.error === 0 && report.summary.failure === 0) {
        info('Appinspect completed without errors or failures');
    }

    if (failOnError && errorCount > 0) {
        throw new Error(`There are ${errorCount} errors/failures to fix.`);
    }
    if (failOnWarning && warningCount > 0) {
        throw new Error(`There are ${warningCount} warnings to fix.`);
    }
}

const splitList = (value: string | null | undefined): string[] | undefined => {
    if (value) {
        return value.trim().split(/\s*,\s*/);
    }
};

async function run(): Promise<void> {
    try {
        const filePath: string = getInput('filePath');
        const user = getInput('splunkUser', { required: true });
        const password = getInput('splunkPassword', { required: true });
        const includedTags = splitList(getInput('includedTags'));
        const excludedTags = splitList(getInput('excludedTags'));
        const failOnError = parseBoolean(getInput('failOnError'), true);
        const failOnWarning = parseBoolean(getInput('failOnWarning'), false);
        const ignoreChecks = splitList(getInput('ignoredChecks'));
        const uploadReportArtifact = parseBoolean(getInput('uploadReportArtifact'));

        await appInspect({
            user,
            password,
            filePath,
            includedTags,
            excludedTags,
            failOnError,
            failOnWarning,
            ignoreChecks,
            uploadReportArtifact,
        });
    } catch (error) {
        setFailed(error.message);
    }
}

run();
