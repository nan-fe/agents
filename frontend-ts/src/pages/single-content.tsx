
import InputForm from '../components/input-form';
import AgentLogs from '../components/agent-logs';
import ResultDisplay from '../components/result-display';
import {LogType} from '../types'

const SingleContent = (props:{
    isLoading: boolean;
    logs: LogType[];
}) => {
    const { isLoading, logs } = props;
    
  return (
              <div className="app">
            {/* <InputForm onSubmit={handleSubmit} isLoading={isLoading} />
            <AgentLogs logs={logs} />
            <ResultDisplay result={result} /> */}
        </div>
  );
};
export default SingleContent;