package com.offtec.hub;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceResponse;
import android.util.Log;
import android.widget.Toast;

public final class MainActivity extends Activity {
    private static final String TAG = "OfftecHubWebView";
    private static final int FILE_PICKER = 72;
    private static final int SAVE_FILE = 73;
    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private String pendingExport;
    private static final String DASHBOARD_URL = "https://appassets.androidplatform.net/index.html";

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        webView = new WebView(this);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        webView.addJavascriptInterface(new HubBridge(), "Offtec");
        webView.setWebViewClient(new WebViewClient() {
            @Override public android.webkit.WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri url = request.getUrl();
                if (!"appassets.androidplatform.net".equals(url.getHost())) {
                    if ("127.0.0.1".equals(url.getHost())) {
                        String origin = request.getRequestHeaders().getOrDefault("Origin", "(sem Origin)");
                        boolean hasAuthorization = request.getRequestHeaders().containsKey("Authorization");
                        Log.i(TAG, "API request: " + request.getMethod() + " " + url + " origin=" + origin
                                + " authorization=" + hasAuthorization);
                    }
                    return super.shouldInterceptRequest(view, request);
                }
                String name = url.getPath().replaceFirst("^/", "");
                Log.d(TAG, "Asset request: " + request.getMethod() + " " + url);
                if (name.isEmpty() || name.contains("..") || name.startsWith("/")) {
                    Log.e(TAG, "Rejected invalid local asset path: " + name);
                    return new android.webkit.WebResourceResponse("text/plain", "UTF-8", 404, "Not Found", null, null);
                }
                try {
                    String lowerName = name.toLowerCase(java.util.Locale.ROOT);
                    String mime = lowerName.endsWith(".html") ? "text/html" : lowerName.endsWith(".css") ? "text/css" : lowerName.endsWith(".js") ? "application/javascript" : "application/octet-stream";
                    WebResourceResponse response = new WebResourceResponse(mime, "UTF-8", 200, "OK", null, getAssets().open(name));
                    Log.i(TAG, "Asset loaded: " + name + " (200, " + mime + ")");
                    return response;
                } catch (java.io.IOException e) {
                    Log.e(TAG, "Asset load failed: " + name + " (404); APK asset path is case-sensitive", e);
                    return new android.webkit.WebResourceResponse("text/plain", "UTF-8", 404, "Not Found", null, null);
                }
            }
            @Override public void onPageFinished(WebView view, String url) {
                Log.i(TAG, "Page finished: " + url);
            }
            @Override public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
                super.onReceivedHttpError(view, request, response);
                Log.e(TAG, "HTTP resource error " + response.getStatusCode() + " " + response.getReasonPhrase()
                        + " at " + request.getUrl() + " (mainFrame=" + request.isForMainFrame() + ")");
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, android.webkit.WebResourceError error) {
                super.onReceivedError(view, request, error);
                Log.e(TAG, "Web resource load error " + error.getErrorCode() + " (" + error.getDescription() + ") at " + request.getUrl() + " (mainFrame=" + request.isForMainFrame() + ")");
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri url = request.getUrl();
                String host = url.getHost();
                boolean local = "https".equals(url.getScheme()) && "appassets.androidplatform.net".equals(host)
                        || "http".equals(url.getScheme()) && "127.0.0.1".equals(host);
                if (!local) Log.w(TAG, "Blocked navigation: " + url);
                return !local;
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                pick.addCategory(Intent.CATEGORY_OPENABLE);
                pick.setType("application/vnd.android.package-archive");
                pick.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"application/vnd.android.package-archive", "application/zip", "application/octet-stream"});
                try { startActivityForResult(pick, FILE_PICKER); return true; }
                catch (ActivityNotFoundException e) { fileCallback = null; return false; }
            }
            @Override public boolean onConsoleMessage(android.webkit.ConsoleMessage message) {
                Log.println(message.messageLevel() == android.webkit.ConsoleMessage.MessageLevel.ERROR ? Log.ERROR : Log.INFO,
                        TAG, "JS " + message.messageLevel() + ": " + message.message() + " (" + message.sourceId() + ":" + message.lineNumber() + ")");
                return true;
            }
        });
        setContentView(webView);
        Log.i(TAG, "Loading bundled dashboard from " + DASHBOARD_URL + "; backend is not required to render the interface");
        webView.loadUrl(DASHBOARD_URL);
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_PICKER && fileCallback != null) {
            Uri[] result = resultCode == RESULT_OK && data != null && data.getData() != null ? new Uri[]{data.getData()} : null;
            fileCallback.onReceiveValue(result);
            fileCallback = null;
        } else if (requestCode == SAVE_FILE) {
            try {
                if (resultCode == RESULT_OK && data != null && data.getData() != null && pendingExport != null) {
                    try (java.io.OutputStream output = getContentResolver().openOutputStream(data.getData())) {
                        if (output != null) output.write(pendingExport.getBytes(java.nio.charset.StandardCharsets.UTF_8));
                    }
                    Toast.makeText(this, "Relatório exportado", Toast.LENGTH_SHORT).show();
                }
            } catch (java.io.IOException e) {
                Toast.makeText(this, "Falha ao salvar o relatório", Toast.LENGTH_LONG).show();
            } finally { pendingExport = null; }
        }
    }

    @Override public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack(); else super.onBackPressed();
    }

    private final class HubBridge {
        @android.webkit.JavascriptInterface public boolean isWebViewInitialized() {
            return webView != null;
        }

        @android.webkit.JavascriptInterface public void saveJson(String json) {
            pendingExport = json;
            runOnUiThread(() -> {
                Intent create = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                create.addCategory(Intent.CATEGORY_OPENABLE);
                create.setType("application/json");
                create.putExtra(Intent.EXTRA_TITLE, "offtec-hub-result.json");
                try { startActivityForResult(create, SAVE_FILE); }
                catch (ActivityNotFoundException e) { pendingExport = null; Toast.makeText(MainActivity.this, "Gerenciador de arquivos indisponível", Toast.LENGTH_LONG).show(); }
            });
        }

        @android.webkit.JavascriptInterface public boolean startTermuxSetup() {
            runOnUiThread(() -> {
                runTermux("/data/data/com.termux/files/home/HUB/termux/install.sh", "Configuração enviada ao Termux");
            });
            return true;
        }

        @android.webkit.JavascriptInterface public boolean startBackend() {
            runOnUiThread(() -> runTermux("/data/data/com.termux/files/home/.local/state/offtec-hub/start.sh", "Inicialização do backend solicitada ao Termux"));
            return true;
        }

        private void runTermux(String script, String successMessage) {
            if (checkSelfPermission("com.termux.permission.RUN_COMMAND") != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{"com.termux.permission.RUN_COMMAND"}, 91);
                Toast.makeText(MainActivity.this, "Conceda Run commands in Termux e toque em Verificar conexão novamente.", Toast.LENGTH_LONG).show();
                return;
            }
            Intent run = new Intent("com.termux.RUN_COMMAND");
            run.setClassName("com.termux", "com.termux.app.RunCommandService");
            run.putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/bash");
            run.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", new String[]{script});
            run.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home");
            run.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
            try {
                startService(run);
                Log.i(TAG, successMessage + ": " + script);
                Toast.makeText(MainActivity.this, successMessage, Toast.LENGTH_SHORT).show();
            } catch (Exception e) {
                Log.e(TAG, "RUN_COMMAND falhou para " + script + "; verifique Termux, allow-external-apps e o caminho do projeto", e);
                Toast.makeText(MainActivity.this, "Não foi possível iniciar pelo Termux. Verifique se está instalado e se Allow external apps está habilitado.", Toast.LENGTH_LONG).show();
            }
        }
    }
}
