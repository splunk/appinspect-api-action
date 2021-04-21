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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getReport = exports.getStatus = exports.submit = exports.login = void 0;
const core_1 = require("@actions/core");
const form_data_1 = __importDefault(require("form-data"));
const fs = __importStar(require("fs"));
const node_fetch_1 = __importDefault(require("node-fetch"));
function req({ url, method, body, headers, }) {
    return __awaiter(this, void 0, void 0, function* () {
        const res = yield node_fetch_1.default(url, {
            method,
            body,
            headers,
        });
        if (!res.ok) {
            try {
                const data = yield res.text();
                throw new Error(`HTTP status ${res.status} from ${url}: ${data}`);
            }
            catch (e) {
                // ignore
            }
            throw new Error(`HTTP status ${res.status} from ${url}`);
        }
        return res.json();
    });
}
function login(user, password) {
    return __awaiter(this, void 0, void 0, function* () {
        core_1.info(`Logging in user ${user}`);
        const basicAuth = Buffer.from(`${user}:${password}`, 'utf-8').toString('base64');
        const auth = yield req({
            method: 'GET',
            url: 'https://api.splunk.com/2.0/rest/login/splunk',
            headers: {
                Authorization: `Basic ${basicAuth}`,
            },
        });
        return auth.data.token;
    });
}
exports.login = login;
function submit({ filePath, includedTags, excludedTags, token, }) {
    return __awaiter(this, void 0, void 0, function* () {
        const form = new form_data_1.default();
        form.append('app_package', fs.createReadStream(filePath));
        if (includedTags) {
            form.append('included_tags', includedTags.join(','));
        }
        if (excludedTags) {
            form.append('excluded_tags', excludedTags.join(','));
        }
        return yield req({
            method: 'POST',
            url: 'https://appinspect.splunk.com/v1/app/validate',
            headers: {
                Authorization: `Bearer ${token}`,
            },
            body: form,
        });
    });
}
exports.submit = submit;
function getStatus(data) {
    return __awaiter(this, void 0, void 0, function* () {
        return req({
            method: 'GET',
            url: `https://appinspect.splunk.com/v1/app/validate/status/${encodeURIComponent(data.request_id)}`,
            headers: {
                Authorization: `Bearer ${data.token}`,
            },
        });
    });
}
exports.getStatus = getStatus;
function getReport(data) {
    return __awaiter(this, void 0, void 0, function* () {
        return req({
            method: 'GET',
            url: `https://appinspect.splunk.com/v1/app/report/${encodeURIComponent(data.request_id)}`,
            headers: {
                Authorization: `Bearer ${data.token}`,
            },
        });
    });
}
exports.getReport = getReport;
