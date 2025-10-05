using System.Collections;
using LexerModule.States;

namespace LexerModule;

internal sealed class LexerStates : IEnumerable<ILexerState>
{
    public ILexerState FindNextTokenState { get; }
    public ILexerState ProcessIdentTokenState { get; }
    public ILexerState ReadSymbolTokenState { get; }
    public ILexerState ReadIdentTokenState { get; }
    public ILexerState EndOfFileState { get; }
    public ILexerState ReadNumberLiteralState { get; }
    public ILexerState ReadTextLiteralState { get; }

    private ILexerState[] _allStates;
    
    public LexerStates()
    {
        FindNextTokenState = new FindNextTokenState(this);
        ReadIdentTokenState = new ReadIdentTokenState(this);
        ProcessIdentTokenState = new ProcessIdentTokenState(this);
        ReadSymbolTokenState = new ReadSymbolState(this);
        ReadNumberLiteralState = new ReadNumberLiteralState(this);
        ReadTextLiteralState = new ReadTextLiteralState(this);
        EndOfFileState = new EndOfFileState();

        _allStates = [
            ReadIdentTokenState,
            ProcessIdentTokenState,
            ReadSymbolTokenState,
            ReadNumberLiteralState,
            ReadTextLiteralState,
            EndOfFileState
        ];
    }

    public IEnumerator<ILexerState> GetEnumerator()
    {
        throw new NotImplementedException();
    }

    IEnumerator IEnumerable.GetEnumerator()
    {
        return GetEnumerator();
    }
}