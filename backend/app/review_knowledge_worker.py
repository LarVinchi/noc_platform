"""Container entry for the optional private accepted-demo worker."""
import uvicorn

if __name__=='__main__':
    uvicorn.run('app.review_rag.noc_service.review_runtime:create_runtime',factory=True,
                host='0.0.0.0',port=8000,access_log=False,log_level='warning')
