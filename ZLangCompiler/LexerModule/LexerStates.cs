using System.Collections;
using LexerModule.States;

namespace LexerModule;

internal sealed class LexerStates : IEnumerable<ILexerState>
{
    private readonly List<ILexerState> _allStates;
    
    public LexerStates()
    {
        _allStates = [
            new ReadIdentState(this),
            new ReadSymbolState(this),
            new ReadNumberLiteralState(this),
            new ReadTextLiteralState(this),
            new EndOfFileState()
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