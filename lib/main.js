"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    Object.defineProperty(o, k2, { enumerable: true, get: function() { return m[k]; } });
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (k !== "default" && Object.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
    __setModuleDefault(result, mod);
    return result;
};
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
Object.defineProperty(exports, "__esModule", { value: true });
const core_1 = require("@actions/core");
const fs = __importStar(require("fs"));
const api_1 = require("./api");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function appInspect({ user, password, filePath, includedTags, excludedTags, }) {
    return __awaiter(this, void 0, void 0, function* () {
        core_1.info(`Submitting file ${filePath} to appinspect API...`);
        if (!fs.existsSync(filePath)) {
            throw new Error(`File ${filePath} does not exist`);
        }
        const token = yield api_1.login(user, password);
        const submitRes = yield api_1.submit({
            filePath,
            token,
            includedTags,
            excludedTags,
        });
        const reqId = submitRes.request_id;
        core_1.info(`Submitted and received reqId=${reqId}`);
        core_1.info('Waiting for appinspect job to complete...');
        while (true) {
            yield sleep(10000);
            const status = yield api_1.getStatus({ request_id: reqId, token });
            core_1.debug(`Got status ${status.status}`);
            if (status.status === 'SUCCESS') {
                break;
            }
            else if (status.status === 'PROCESSING') {
                core_1.debug('Appinspect job is still processing');
            }
            else {
                throw new Error(`Unexpected status ${status.status}`);
            }
        }
        core_1.info(`Retrieving report for reqId=${reqId}`);
        const reportDoc = yield api_1.getReport({ request_id: reqId, token });
        if (reportDoc.reports.length !== 1) {
            core_1.warning(`Received ${reportDoc.reports.length} report documents. Expected 1.`);
        }
        const report = reportDoc.reports[0];
        core_1.info(`Received report for app: ${report.app_name} ${report.app_version} [${report.app_hash}]`);
        core_1.info(`Tags: ${report.run_parameters.included_tags.join(',')} - excluded: ${report.run_parameters.excluded_tags.join(',')}`);
        core_1.info(`Summary: ${JSON.stringify(report.summary, null, 2)}`);
        for (const group of report.groups) {
            for (const check of group.checks) {
                switch (check.result) {
                    case 'error':
                    case 'failure':
                        core_1.error(`${check.result.toUpperCase()}: ${check.name}\n${check.description}\n${(check.messages || [])
                            .map((m) => m.message)
                            .join('\n')}\nTags: ${check.tags.join(',')}`);
                        break;
                    case 'warning':
                        core_1.warning(`Warning: ${check.name}\n${check.description}\n${(check.messages || [])
                            .map((m) => m.message)
                            .join('\n')}\nTags: ${check.tags.join(',')}`);
                        break;
                    case 'manual_check':
                        core_1.debug(`Check ${check.name} requires a manual check`);
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
        if (report.summary.error === 0 && report.summary.failure === 0) {
            core_1.info('Appinspect completed without errors or failures');
        }
    });
}
const splitTags = (value) => {
    if (value) {
        return value.trim().split(/\s*,\s*/);
    }
};
function run() {
    return __awaiter(this, void 0, void 0, function* () {
        try {
            const filePath = core_1.getInput('filePath');
            const user = core_1.getInput('splunkUser');
            const password = core_1.getInput('splunkPassword');
            const includedTags = splitTags(core_1.getInput('includedTags'));
            const excludedTags = splitTags(core_1.getInput('includedTags'));
            yield appInspect({ user, password, filePath, includedTags, excludedTags });
        }
        catch (error) {
            core_1.setFailed(error.message);
        }
    });
}
run();
