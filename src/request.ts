// See: https://stackoverflow.com/questions/30008114/how-do-i-promisify-native-xhr#30008115

export type BagOfStrings = {
  [key: string]: string
}

export interface Options {
  url: string;
  method?: string;
  responseType?: XMLHttpRequestResponseType;
  headers?: BagOfStrings;
  binary?: boolean;
  data?: BagOfStrings | XMLHttpRequestBodyInit;
}

export function request(opts: Options) : Promise<XMLHttpRequest> {
  return new Promise(function(resolve, reject) {
    const xhr = new XMLHttpRequest();
    xhr.open(opts.method || 'GET', opts.url);
    if (opts.responseType) xhr.responseType = opts.responseType;
    xhr.onload = function () {
      if (this.status >= 200 && this.status < 300) resolve(xhr);
      else reject(this);
    };
    xhr.onerror = function () {
      reject(this);
    };
    if (opts.headers) {
      Object.keys(opts.headers).forEach(key => xhr.setRequestHeader(key, opts.headers![key]));
    }
    let params = opts.data;
    // We'll need to stringify if we've been given an object
    // If we have a string, this is skipped.
    if (params && typeof params === 'object' && !opts.binary) {
      const qs = new URLSearchParams();
      Object.keys(params).forEach(key => qs.set(key, (params as BagOfStrings)[key]));
      params = qs;
    }
    xhr.send(params as XMLHttpRequestBodyInit);
  });
}
