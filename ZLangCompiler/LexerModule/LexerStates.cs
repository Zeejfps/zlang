using System.Collections;
using LexerModule.States;

namespace LexerModule;

internal sealed class LexerStates : IEnumerable<ILexerState>
{
    public ILexerState FindNextTokenState { get; }
    public ILexerState ReadSymbolTokenState { get; }
    public ILexerState ReadIdentTokenState { get; }
    public ILexerState EndOfFileState { get; }
    public ILexerState ReadNumberLiteralState { get; }
    public ILexerState ReadTextLiteralState { get; }

    private readonly List<ILexerState> _allStates;
    
    public LexerStates()
    {
        FindNextTokenState = new FindNextTokenState(this);
        ReadIdentTokenState = new ReadIdentState(this);
        ReadSymbolTokenState = new ReadSymbolState(this);
        ReadNumberLiteralState = new ReadNumberLiteralState(this);
        ReadTextLiteralState = new ReadTextLiteralState(this);
        EndOfFileState = new EndOfFileState();

        _allStates = [
            ReadIdentTokenState,
            ReadSymbolTokenState,
            ReadNumberLiteralState,
            ReadTextLiteralState,
            EndOfFileState
        ];
    }

    public IEnumerator<ILexerState> GetEnumerator()
    {
        return _allStates.GetEnumerator();
    }

    IEnumerator IEnumerable.GetEnumerator()
    {
        return GetEnumerator();
    }
}